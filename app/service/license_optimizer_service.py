from __future__ import annotations

import json
import os
import datetime
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import inspect as sqla_inspect
from sqlalchemy.orm import Session

from app.core.logger import setup_logger
from app.models.database import engine, SessionLocal
from app.models.dynamic_models import (
    create_AGR1251_model,
    create_AGRUSERS_model,
    create_AGRDEFINE_model,
    create_FLPCA_model,
    create_role_lic_model,
    create_role_lic_summary_model,
    create_TSTCT_model,
    create_USOBXC_model,
    create_TOBJL_model,
)
from app.models.request_array import RequestArray
from app.models.Opt_results import (
    LicenseOptimizationResult,
    create_opt_sim_result_model,
)
from app.models.client_sys_release_version import actvtText          # ← NEW import
from app.service.chatgpt import call_ai_api

logger = setup_logger("app_logger")


# ---------------------------------------------------------------------------
# License tier ordering  (higher index = more restrictive = higher FUE cost)
# ---------------------------------------------------------------------------
_LICENSE_RANK: Dict[str, int] = {
    "GD Self-Service Use": 1,
    "GC Core Use":         2,
    "GB Advanced Use":     3,
    "Not Classified":      0,
}

_FUE_WEIGHT: Dict[str, float] = {
    "GB Advanced Use":     1.00,
    "GC Core Use":         0.20,
    "GD Self-Service Use": 0.033,
    "Not Classified":      0.00,
}


def _rank(license_name: Optional[str]) -> int:
    if not license_name:
        return 0
    for key, rank in _LICENSE_RANK.items():
        if key.lower() in license_name.lower():
            return rank
    return 3


def _weight(license_name: Optional[str]) -> float:
    if not license_name:
        return 0.0
    for key, w in _FUE_WEIGHT.items():
        if key.lower() in license_name.lower():
            return w
    return 1.0


def _most_restrictive(licenses: List[Optional[str]]) -> str:
    best = "Not Classified"
    best_rank = 0
    for lic in licenses:
        if lic and _rank(lic) > best_rank:
            best_rank = _rank(lic)
            best = lic
    return best


# ---------------------------------------------------------------------------
# Ensure a table exists
# ---------------------------------------------------------------------------
def _ensure_table(model_class) -> None:
    inspector = sqla_inspect(engine)
    if not inspector.has_table(model_class.__tablename__):
        logger.info(f"Creating table '{model_class.__tablename__}'")
        model_class.__table__.create(bind=engine)


# ---------------------------------------------------------------------------
# Helper: Get object description from TOBJL
# ---------------------------------------------------------------------------
def _get_object_description(db: Session, system_name: str, auth_object: str) -> str:
    try:
        TOBJLModel = create_TOBJL_model(system_name)
        result = db.query(TOBJLModel.TEXT).filter(
            TOBJLModel.AUTH_OBJ == auth_object
        ).first()
        return result.TEXT if result and result.TEXT else ""
    except Exception as exc:
        logger.warning(f"Failed to get description for object '{auth_object}': {exc}")
        return ""


# ---------------------------------------------------------------------------
# Helper: Get possible values from ruleset (RoleLic)
# ---------------------------------------------------------------------------
def _get_possible_values_from_ruleset(
    db: Session,
    system_name: str,
    auth_object: str,
    field: str
) -> str:
    try:
        RoleLic = create_role_lic_model(system_name)
        results = db.query(RoleLic.LOW).filter(
            RoleLic.OBJECT == auth_object,
            RoleLic.FIELD == field,
            RoleLic.LOW.isnot(None)
        ).distinct().all()
        values = [r.LOW for r in results if r.LOW]
        return ", ".join(sorted(set(values))) if values else ""
    except Exception as exc:
        logger.warning(f"Failed to get possible values for {auth_object}/{field}: {exc}")
        return ""


# ---------------------------------------------------------------------------
# Helper: Get transaction code description
# ---------------------------------------------------------------------------
def _get_tcode_description(db: Session, system_name: str, tcode: str) -> str:
    try:
        TSTCTModel = create_TSTCT_model(system_name)
        result = db.query(TSTCTModel.TRANSACTION_TEXT).filter(
            TSTCTModel.TCODE == tcode
        ).first()
        return result.TRANSACTION_TEXT if result and result.TRANSACTION_TEXT else ""
    except Exception as exc:
        logger.warning(f"Failed to get description for tcode '{tcode}': {exc}")
        return ""


# ---------------------------------------------------------------------------
# NEW Helper: Get ACTVT descriptions for a list of values
# ---------------------------------------------------------------------------
def _get_actvt_descriptions(db: Session, values: List[str]) -> Dict[str, str]:
    """
    Fetch activity text descriptions for a list of ACTVT values.
    Returns a dict: {"01": "Create", "02": "Change", ...}
    Uses the global Z_ACTVT_TEXT table (not system-specific).
    """
    if not values:
        return {}
    try:
        rows = db.query(actvtText.ACTIVITY, actvtText.TEXT).filter(
            actvtText.ACTIVITY.in_(values)
        ).all()
        return {row.ACTIVITY: row.TEXT for row in rows if row.ACTIVITY and row.TEXT}
    except Exception as exc:
        logger.warning(f"Failed to get ACTVT descriptions: {exc}")
        return {}


# ---------------------------------------------------------------------------
# Helper: Build enhanced authorization objects with merging + ACTVT enrichment
# ---------------------------------------------------------------------------
def _build_enhanced_auth_objects(
    db: Session,
    system_name: str,
    role: str,
    role_rows: List,
    role_tcodes: Set[str]
) -> List[Dict[str, Any]]:
    """
    Build authorization objects list with:
    1. Merging: same object+field with multiple values → single entry, values comma-joined
    2. ACTVT enrichment: resolve activity codes to descriptions
    3. Manual (OBJ_STATUS='U') vs system-added distinction — evaluated at the
       AUTH OBJECT level (across all its fields/values), not per (object, field)
    4. Relevant transaction codes for system-added objects
    """
    AGR1251     = create_AGR1251_model(system_name)
    USOBXCModel = create_USOBXC_model(system_name)

    # ---- Fetch OBJ_STATUS for all rows of this role from AGR1251 ----
    agr1251_rows = db.query(
        AGR1251.OBJECT,
        AGR1251.FIELD,
        AGR1251.LOW,
        AGR1251.OBJ_STATUS
    ).filter(AGR1251.AGR_NAME == role).all()

    # Map (object, field, value) → obj_status
    obj_status_map: Dict[Tuple, str] = {
        (row.OBJECT, row.FIELD, row.LOW): row.OBJ_STATUS
        for row in agr1251_rows
    }

    # ---- Object-level system-added flag ----
    # An auth object is treated as "system-added" if ANY row for that object
    # — across ALL fields and values, not just one specific field/value —
    # has OBJ_STATUS != 'U'. This means a fully-manual (object, field) group
    # still gets its relevant tcodes looked up if some other field/value
    # under the same object was system-added.
    system_added_objects: Set[str] = {
        row.OBJECT for row in agr1251_rows if row.OBJ_STATUS != "U"
    }

    # ---- Step 1: Group role_rows by (object, field) and merge values ----
    # grouped[(object, field)] = {
    #   "values": [v1, v2, ...],
    #   "description": "...",
    #   "possibleValues": "...",
    #   "obj_status": "U" | "" | ...   (use most permissive — if ANY value is not 'U', treat as system)
    # }
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for r in role_rows:
        key = (r.OBJECT, r.FIELD)
        val = r.LOW or ""

        if key not in grouped:
            desc          = _get_object_description(db, system_name, r.OBJECT)
            possible_vals = _get_possible_values_from_ruleset(db, system_name, r.OBJECT, r.FIELD)
            grouped[key] = {
                "object":         r.OBJECT,
                "field":          r.FIELD,
                "values":         [],
                "description":    desc,
                "possibleValues": possible_vals,
                "obj_statuses":   [],
            }

        if val and val not in grouped[key]["values"]:
            grouped[key]["values"].append(val)

        obj_st = obj_status_map.get((r.OBJECT, r.FIELD, r.LOW), "")
        grouped[key]["obj_statuses"].append(obj_st)

    # ---- Step 2: Build final auth_objects list ----
    auth_objects: List[Dict[str, Any]] = []

    for (obj_name, field_name), data in grouped.items():
        values = sorted(data["values"])

        # Object-level check: treat the whole object as system-added if ANY
        # field/value under it was system-added — even if this specific
        # field/value group is itself 100% manually added.
        is_manual = obj_name not in system_added_objects

        # ---- ACTVT enrichment ----
        value_descriptions = ""
        if field_name == "ACTVT" and values:
            actvt_map = _get_actvt_descriptions(db, values)
            if actvt_map:
                parts = []
                for v in values:
                    text = actvt_map.get(v, "")
                    parts.append(f"{v} ({text})" if text else v)
                value_descriptions = ", ".join(parts)

        auth_obj_dict: Dict[str, Any] = {
            "object":            obj_name,
            "field":             field_name,
            "value":             ", ".join(values),          # merged values
            "description":       data["description"],
            "possibleValues":    data["possibleValues"],
        }

        # Add ACTVT descriptions only when we resolved something
        if value_descriptions:
            auth_obj_dict["valueDescriptions"] = value_descriptions

        if is_manual:
            # Manually added — no tcode mapping needed
            logger.debug(f"[{role}] Manual object: {obj_name}/{field_name}={values}")
        else:
            # System-added (object-level) — find relevant transaction codes via USOBXC
            try:
                usobxc_rows = db.query(USOBXCModel.NAME).filter(
                    USOBXCModel.AUTH_OBJ   == obj_name,
                    USOBXCModel.OKFLAG     == "Y",
                    USOBXCModel.PROPOSED_VALUE_FOR == "TR"
                ).distinct().all()

                relevant_tcodes = [
                    row.NAME for row in usobxc_rows
                    if row.NAME and row.NAME in role_tcodes
                ]

                if relevant_tcodes:
                    tcode_with_desc = []
                    for tcode in relevant_tcodes:
                        desc = _get_tcode_description(db, system_name, tcode)
                        tcode_with_desc.append(f"{tcode} ({desc})" if desc else tcode)
                    auth_obj_dict["relevantTransactionCodes"] = ", ".join(sorted(tcode_with_desc))
                    logger.debug(
                        f"[{role}] System object: {obj_name}/{field_name} "
                        f"→ {len(relevant_tcodes)} relevant tcodes"
                    )
                else:
                    auth_obj_dict["relevantTransactionCodes"] = ""

            except Exception as exc:
                logger.warning(f"[{role}] USOBXC fetch failed for {obj_name}: {exc}")
                auth_obj_dict["relevantTransactionCodes"] = ""

        auth_objects.append(auth_obj_dict)

    return auth_objects


# ---------------------------------------------------------------------------
# Helper: Build enhanced transaction codes list
# ---------------------------------------------------------------------------
def _build_enhanced_tcodes(
    db: Session,
    system_name: str,
    role: str,
    tcode_list: List[str]
) -> List[Dict[str, str]]:
    enhanced_tcodes = []
    for tcode in sorted(tcode_list):
        desc = _get_tcode_description(db, system_name, tcode)
        enhanced_tcodes.append({"tcode": tcode, "description": desc})
    return enhanced_tcodes


# ---------------------------------------------------------------------------
# Helper: Write prompt to file for debugging
# ---------------------------------------------------------------------------
def _write_prompt_debug_file(system_name: str, request_id: str, prompt: str) -> None:
    try:
        os.makedirs("output/prompts", exist_ok=True)
        ts       = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"output/prompts/{system_name}-{request_id}-{ts}-prompt.txt"
        with open(filename, "w", encoding="utf-8") as fh:
            fh.write(prompt)
        logger.info(f"[{request_id}] Full prompt written to: {filename}")
    except Exception as exc:
        logger.error(f"[{request_id}] Failed to write prompt file: {exc}", exc_info=True)


# ---------------------------------------------------------------------------
# 1. Create request record immediately
# ---------------------------------------------------------------------------
async def create_optimization_request_immediately(
    db: Session,
    system_name: str,
) -> str:
    logger.info(f"Creating optimisation request for system='{system_name}'.")
    _ensure_table(RequestArray)
    _ensure_table(LicenseOptimizationResult)

    latest = (
        db.query(RequestArray)
        .filter(RequestArray.req_id.like("REQ%"))
        .order_by(RequestArray.req_id.desc())
        .first()
    )
    if latest and latest.req_id.startswith("REQ"):
        try:
            next_num = int(latest.req_id[3:]) + 1
        except ValueError:
            next_num = 100000
    else:
        next_num = 100000

    req_id = f"REQ{next_num}"
    db.add(RequestArray(req_id=req_id, SYSTEM_NAME=system_name, STATUS="IN_PROGRESS"))
    db.commit()
    logger.info(f"Request record '{req_id}' committed.")
    return req_id


# ---------------------------------------------------------------------------
# 2. Background entry-point
# ---------------------------------------------------------------------------
def process_optimization_in_background(
    system_name: str,
    request_id: str,
    target_license: str,
    sap_system_info: str,
    role_names: Optional[List[str]],
    ratio_threshold: Optional[int],
) -> None:
    db     = SessionLocal()
    status = "FAILED"
    error_message = None
    try:
        logger.info(f"[{request_id}] Background optimisation started.")
        result = run_optimization_processing(
            db=db,
            system_name=system_name,
            request_id=request_id,
            target_license=target_license,
            sap_system_info=sap_system_info,
            role_names=role_names,
            ratio_threshold=ratio_threshold,
        )
        if isinstance(result, dict) and "error" in result:
            status = "FAILED"
            error_message = result["error"]  # ← ADD: e.g. "AI API call failed: Your credit balance is too low..."
        elif isinstance(result, dict) and "message" in result:
            status = "FAILED"
            error_message = result["message"]  # ← ADD: handles the 404 "no roles found" case too
        else:
            status = "COMPLETED"

        logger.info(f"[{request_id}] Processing finished → STATUS={status}")
    except Exception as exc:
        logger.error(f"[{request_id}] Unhandled background exception: {exc}", exc_info=True)
        error_message = str(exc)  # ← ADD: catch unhandled exceptions too

    finally:
        try:
            req_row = db.query(RequestArray).filter(RequestArray.req_id == request_id).first()
            if req_row:
                req_row.STATUS = status
                req_row.ERROR_MESSAGE = error_message  # ← ADD
                db.commit()
        except Exception as upd_exc:
            logger.error(f"[{request_id}] Failed to update status: {upd_exc}", exc_info=True)
        db.close()
    #     status = "FAILED" if isinstance(result, dict) and "error" in result else "COMPLETED"
    #     logger.info(f"[{request_id}] Processing finished → STATUS={status}")
    # except Exception as exc:
    #     logger.error(f"[{request_id}] Unhandled background exception: {exc}", exc_info=True)
    # finally:
    #     try:
    #         req_row = db.query(RequestArray).filter(RequestArray.req_id == request_id).first()
    #         if req_row:
    #             req_row.STATUS = status
    #             db.commit()
    #     except Exception as upd_exc:
    #         logger.error(f"[{request_id}] Failed to update status: {upd_exc}", exc_info=True)
    #     db.close()


# ---------------------------------------------------------------------------
# 3. Core processing logic
# ---------------------------------------------------------------------------
def run_optimization_processing(
    db: Session,
    system_name: str,
    request_id: str,
    target_license: str,
    sap_system_info: str,
    role_names: Optional[List[str]],
    ratio_threshold: Optional[int],
) -> Dict[str, Any]:

    logger.info(
        f"[{request_id}] run_optimization_processing() — "
        f"system={system_name}, target_license={target_license}, roles={role_names or 'ALL'}"
    )

    inspector = sqla_inspect(engine)

    # ---- Resolve dynamic models ----
    RoleLic        = create_role_lic_model(system_name)
    RoleLicSummary = create_role_lic_summary_model(system_name)
    AGR1251        = create_AGR1251_model(system_name)
    AGRUsers       = create_AGRUSERS_model(system_name)
    AGRDefine      = create_AGRDEFINE_model(system_name)
    OptSimResult   = create_opt_sim_result_model(system_name)
    _ensure_table(OptSimResult)

    # ---- Validate required tables ----
    for model, label in [
        (RoleLic,        "RoleLic"),
        (RoleLicSummary, "RoleLicSummary"),
        (AGR1251,        "AGR1251"),
        (AGRUsers,       "AGRUsers"),
    ]:
        if not inspector.has_table(model.__tablename__):
            msg = f"Required table '{model.__tablename__}' ({label}) not found. Load data first."
            logger.error(f"[{request_id}] {msg}")
            return {"error": msg, "status_code": 404}

    has_agrdefine = inspector.has_table(AGRDefine.__tablename__)
    if not has_agrdefine:
        logger.warning(f"[{request_id}] AGRDEFINE table missing — role descriptions will be empty.")

    # Optional FLPCA (Fiori)
    FLPCAModel = None
    try:
        FLPCAModel = create_FLPCA_model(system_name)
        if not inspector.has_table(FLPCAModel.__tablename__):
            FLPCAModel = None
    except Exception:
        FLPCAModel = None
    if not FLPCAModel:
        logger.warning(f"[{request_id}] FLPCA table missing — Fiori data omitted.")

    # ---- Query RoleLic rows for the target license ----
    query = db.query(RoleLic).filter(RoleLic.CLASSIFY_LIC == target_license)
    if role_names:
        query = query.filter(RoleLic.AGR_NAME.in_(role_names))
    roles_data = query.all()
    logger.info(f"[{request_id}] RoleLic rows fetched: {len(roles_data)}")

    if not roles_data:
        msg = (
            f"No roles found with license '{target_license}' for system '{system_name}'"
            + (f" and roles {role_names}" if role_names else "")
        )
        logger.info(f"[{request_id}] {msg}")
        return {"message": msg, "status_code": 404}

    distinct_roles: List[str] = sorted({r.AGR_NAME for r in roles_data})
    logger.info(f"[{request_id}] Distinct roles to analyse: {distinct_roles}")

    # ---- Role descriptions from AGRDEFINE ----
    role_descriptions: Dict[str, str] = {}
    if has_agrdefine:
        for row in db.query(AGRDefine).filter(AGRDefine.AGR_NAME.in_(distinct_roles)).all():
            if row.AGR_NAME and row.TEXT:
                role_descriptions[row.AGR_NAME] = row.TEXT

    # ---- Build per-role JSON payload for AI ----
    all_roles_json: List[Dict] = []
    for role in distinct_roles:
        role_rows = [r for r in roles_data if r.AGR_NAME == role]
        if not role_rows:
            continue

        # Extract all transaction codes for this role
        tcodes_query = (
            db.query(AGR1251.LOW)
            .filter(
                AGR1251.AGR_NAME == role,
                AGR1251.OBJECT   == "S_TCODE",
                AGR1251.FIELD    == "TCD"
            )
            .distinct().all()
        )
        role_tcodes: Set[str] = {t.LOW for t in tcodes_query if t.LOW}
        logger.info(f"[{request_id}] Role '{role}' has {len(role_tcodes)} tcodes")

        # Build enhanced + merged authorization objects
        auth_objects = _build_enhanced_auth_objects(
            db, system_name, role, role_rows, role_tcodes
        )

        # Build enhanced transaction codes list with descriptions
        enhanced_tcodes = _build_enhanced_tcodes(
            db, system_name, role, list(role_tcodes)
        )

        # Fiori apps
        fiori_apps: List[Dict] = []
        if FLPCAModel:
            try:
                seen: Dict[str, Dict] = {}
                for fr in db.query(FLPCAModel).filter(FLPCAModel.Single_Role_Name == role).all():
                    app = fr.Title_Subtitle_Information
                    act = fr.Semantic_Object_Action
                    if app and app.strip():
                        if app not in seen:
                            seen[app] = {"app": app, "actions": []}
                        if act and act.strip() and act not in seen[app]["actions"]:
                            seen[app]["actions"].append(act)
                fiori_apps = list(seen.values())
            except Exception as fe:
                logger.warning(f"[{request_id}] Fiori fetch failed for '{role}': {fe}")

        all_roles_json.append({
            "role":                 role,
            "roleDescription":      role_descriptions.get(role, "No description available"),
            "currentLicense":       target_license,
            "authorizationObjects": auth_objects,
            "transactionCodes":     enhanced_tcodes,
            "fioriApps":            fiori_apps,
        })

    logger.info(f"[{request_id}] Roles packaged for AI: {len(all_roles_json)}")
    if not all_roles_json:
        return {"message": "No role data to send to AI.", "status_code": 404}

    # ---- Build AI prompt (system header removed) ----
    prompt = f"""You are an SAP FUE licence optimisation expert.

The {len(all_roles_json)} role(s) below are currently classified as "{target_license}".
For EACH role, decide if the overall role licence can be reduced, and provide:
  1. A role-level licence suggestion (suggestedRoleLicense).
  2. Per auth-object analysis.

Field reference:
- "value": current assigned value(s), comma-separated when multiple
- "valueDescriptions": human-readable labels for ACTVT codes (e.g. "01 (Create), 02 (Change)")
- "possibleValues": all values available in the ruleset for this object/field
- "relevantTransactionCodes": transactions that require this auth object (system-added objects only)
- "description": auth object description

Role data:
{json.dumps(all_roles_json, indent=2)}

Return ONLY a valid JSON array — no markdown, no preamble — in EXACTLY this structure:
[
  {{
    "role": "<AGR_NAME>",
    "suggestedRoleLicense": "<GB Advanced Use | GC Core Use | GD Self-Service Use | No Change>",
    "objects": [
      {{
        "authorizationObject": "<OBJECT>",
        "field":               "<FIELD>",
        "value":               "<VALUE>",
        "licenseCanBeReduced": "Yes | No | May Be",
        "insights":            "<short reason>",
        "recommendation":      "<short action>",
        "explanation":         "<detailed analysis considering transaction codes, value descriptions and possible values>"
      }}
    ]
  }}
]
"""

    logger.info(f"[{request_id}] Sending prompt to AI (length={len(prompt)}).")
    _write_prompt_debug_file(system_name, request_id, prompt)

    try:
        ai_raw = call_ai_api(prompt)
        logger.debug(f"[{request_id}] AI raw (first 500): {ai_raw[:500]}")
    except Exception as ai_exc:
        logger.error(f"[{request_id}] AI call failed: {ai_exc}", exc_info=True)
        return {"error": f"AI API call failed: {ai_exc}", "status_code": 502}

    # Strip markdown fences
    ai_clean = ai_raw.strip()
    for fence in ("```json", "```"):
        if ai_clean.startswith(fence):
            ai_clean = ai_clean[len(fence):]
            break
    if ai_clean.endswith("```"):
        ai_clean = ai_clean[:-3]
    ai_clean = ai_clean.strip()

    # try:
    #     ai_roles: List[Dict] = json.loads(ai_clean)
    #     logger.info(f"[{request_id}] AI returned {len(ai_roles)} role block(s).")
    # except json.JSONDecodeError as je:
    #     logger.error(f"[{request_id}] JSON parse failed: {je}\nRaw:\n{ai_raw[:1000]}")
    #     return {"error": f"Failed to parse AI response: {je}", "status_code": 502}
    try:
        ai_roles: List[Dict] = json.loads(ai_clean)
        logger.info(f"[{request_id}] AI returned {len(ai_roles)} role block(s).")
        for rb in ai_roles:
            role_val = rb.get("role", "MISSING")
            objects_val = rb.get("objects", rb.get("authorizationObjects", []))
            logger.info(f"[{request_id}]   → role='{role_val}' objects={len(objects_val)}")
    except json.JSONDecodeError as je:
        logger.error(f"[{request_id}] JSON parse failed: {je}\nRaw:\n{ai_raw[:2000]}")
        return {"error": f"Failed to parse AI response: {je}", "status_code": 502}

    # ---- Write LicenseOptimizationResult rows + collect reducibility ----
    reducible_roles: Dict[str, str] = {}
    results_by_role: Dict[str, List[Dict]] = {}

    for role_block in ai_roles:
        role_name = role_block.get("role", "")
        suggested_role_lic = role_block.get("suggestedRoleLicense", "")
        objects = role_block.get("objects", [])

        # ── PROBLEM: Claude sometimes returns placeholder text like "<AGR_NAME>"
        # when the role data in the prompt was malformed. Skip those.
        if not role_name or role_name.startswith("<"):
            logger.warning(f"[{request_id}] Skipping placeholder role block: '{role_name}'")
            continue

        # ── PROBLEM: "objects" key might be named differently in Claude's response
        # Claude sometimes returns "authorizationObjects" instead of "objects"
        if not objects:
            objects = role_block.get("authorizationObjects", [])

        desc = role_descriptions.get(role_name, "No description available")

        # ── Reducibility check ──
        statuses = [obj.get("licenseCanBeReduced", "No").strip().lower() for obj in objects]
        is_reducible = (
                bool(objects)
                and all(s in ("yes", "may be") for s in statuses)
                and bool(suggested_role_lic)
                and suggested_role_lic not in ("No Change", "GB Advanced Use")
                and not suggested_role_lic.startswith("<")
        )

        if is_reducible:
            reducible_roles[role_name] = suggested_role_lic
            logger.info(f"[{request_id}] Role '{role_name}' → REDUCIBLE → '{suggested_role_lic}'")
        else:
            logger.info(f"[{request_id}] Role '{role_name}' → NOT reducible")

        # ── Save each object row to DB ──
        for obj in objects:
            # Skip placeholder objects
            auth_obj_val = obj.get("authorizationObject", "")
            if not auth_obj_val or auth_obj_val.startswith("<"):
                logger.warning(f"[{request_id}] Skipping placeholder object in role '{role_name}'")
                continue

            db_row = LicenseOptimizationResult(
                REQ_ID=request_id,
                ROLE_ID=role_name,
                ROLE_DESCRIPTION=desc,
                AUTHORIZATION_OBJECT=auth_obj_val,
                FIELD=obj.get("field", ""),
                VALUE=obj.get("value", ""),
                LICENSE_REDUCIBLE=obj.get("licenseCanBeReduced", ""),
                SUGGESTED_ROLE_LICENSE=suggested_role_lic,
                INSIGHTS=obj.get("insights", ""),
                RECOMMENDATIONS=obj.get("recommendation", ""),
                EXPLANATIONS=obj.get("explanation", ""),
            )
            db.add(db_row)

        results_by_role[role_name] = objects
        logger.info(f"[{request_id}] Saved {len(objects)} objects for role '{role_name}'")
    # # ---- Write LicenseOptimizationResult rows + collect reducibility ----
    # reducible_roles: Dict[str, str] = {}
    # results_by_role: Dict[str, List[Dict]] = {}
    #
    # for role_block in ai_roles:
    #     role_name          = role_block.get("role", "")
    #     suggested_role_lic = role_block.get("suggestedRoleLicense", "")
    #     objects            = role_block.get("objects", [])
    #
    #     if not role_name:
    #         logger.warning(f"[{request_id}] AI block missing 'role' — skipping.")
    #         continue
    #
    #     desc = role_descriptions.get(role_name, "No description available")
    #
    #     statuses         = [obj.get("licenseCanBeReduced", "No").strip().lower() for obj in objects]
    #     all_yes_or_maybe = all(s in ("yes", "may be") for s in statuses)
    #     is_reducible     = all_yes_or_maybe and bool(suggested_role_lic) and suggested_role_lic != "No Change"
    #
    #     if is_reducible:
    #         reducible_roles[role_name] = suggested_role_lic
    #         logger.info(f"[{request_id}] Role '{role_name}' → REDUCIBLE → '{suggested_role_lic}'")
    #     else:
    #         logger.info(f"[{request_id}] Role '{role_name}' → NOT reducible")
    #
    #     for obj in objects:
    #         db_row = LicenseOptimizationResult(
    #             REQ_ID                 = request_id,
    #             ROLE_ID                = role_name,
    #             ROLE_DESCRIPTION       = desc,
    #             AUTHORIZATION_OBJECT   = obj.get("authorizationObject", ""),
    #             FIELD                  = obj.get("field", ""),
    #             VALUE                  = obj.get("value", ""),
    #             LICENSE_REDUCIBLE      = obj.get("licenseCanBeReduced", ""),
    #             SUGGESTED_ROLE_LICENSE = suggested_role_lic,
    #             INSIGHTS               = obj.get("insights", ""),
    #             RECOMMENDATIONS        = obj.get("recommendation", ""),
    #             EXPLANATIONS           = obj.get("explanation", ""),
    #         )
    #         db.add(db_row)
    #
    #     results_by_role[role_name] = objects

    db.commit()
    logger.info(
        f"[{request_id}] LicenseOptimizationResult committed. "
        f"Reducible roles: {list(reducible_roles.keys())}"
    )

    simulate_system_fue(
        db=db,
        system_name=system_name,
        request_id=request_id,
        reducible_roles=reducible_roles,
        agr_users_model=AGRUsers,
        role_lic_summary_model=RoleLicSummary,
        opt_sim_result_model=OptSimResult,
    )

    _write_output_file(system_name, request_id, results_by_role)

    logger.info(f"[{request_id}] run_optimization_processing() complete.")
    return results_by_role


# ---------------------------------------------------------------------------
# 4. Full-system FUE simulation
# ---------------------------------------------------------------------------
def simulate_system_fue(
    db: Session,
    system_name: str,
    request_id: str,
    reducible_roles: Dict[str, str],
    agr_users_model,
    role_lic_summary_model,
    opt_sim_result_model,
) -> None:
    import math
    from app.models.dynamic_models import create_user_lic_summary_model, create_user_lic_model

    FUE_FACTORS = {
        "GB Advanced Use":     1.0,
        "GC Core Use":         0.2,
        "GD Self-Service Use": 0.0333,
    }

    logger.info(
        f"[{request_id}] simulate_system_fue() — "
        f"{len(reducible_roles)} reducible role(s): {list(reducible_roles.keys())}"
    )

    try:
        # ── STEP 1: Load UserLicSummary as the authoritative BEFORE baseline ──
        # This is EXACTLY what the dashboard reads — guarantees before_total_fue
        # will always match the dashboard FUE figure.
        UserLicSummaryModel = create_user_lic_summary_model(system_name)
        summary_rows = db.query(UserLicSummaryModel).all()

        if not summary_rows:
            logger.warning(f"[{request_id}] UserLicSummary is empty — run Stage 5 first.")
            return

        logger.info(f"[{request_id}] UserLicSummary rows loaded: {len(summary_rows)}")

        # Build: user → current license (the BEFORE state)
        user_before: Dict[str, str] = {
            row.UNAME: (row.CLASSIFY_LIC or "Not Classified")
            for row in summary_rows
        }

        # ── STEP 2: Load UserRoleLlic to know which roles each user has ────────
        # We need this to apply the reducible_roles overrides per user.
        UserRoleLicModel = create_user_lic_model(system_name)
        user_role_rows = db.query(
            UserRoleLicModel.UNAME,
            UserRoleLicModel.AGR_NAME,
            UserRoleLicModel.CLASSIFY_LIC,
        ).all()

        # Build: user → list of (role, license) pairs
        user_roles: Dict[str, List[tuple]] = defaultdict(list)
        for row in user_role_rows:
            if row.UNAME and row.AGR_NAME:
                user_roles[row.UNAME].append((row.AGR_NAME, row.CLASSIFY_LIC or "Not Classified"))

        logger.info(f"[{request_id}] UserRoleLlic rows loaded: {len(user_role_rows)}")

        # # ── STEP 3: Compute AFTER state ────────────────────────────────────────
        # # For each user, replace any reducible role's license with the new one,
        # # then re-derive the most restrictive license across all their roles.
        # user_after: Dict[str, str] = {}
        #
        # for uname in user_before:
        #     roles = user_roles.get(uname, [])
        #
        #     if not roles:
        #         # User exists in UserLicSummary but has no role rows —
        #         # keep their current license unchanged
        #         user_after[uname] = user_before[uname]
        #         continue
        #
        #     # Re-evaluate each role license, applying overrides
        #     simulated_licenses = []
        #     for (role_name, role_lic) in roles:
        #         if role_name in reducible_roles:
        #             simulated_licenses.append(reducible_roles[role_name])
        #         else:
        #             simulated_licenses.append(role_lic)
        #
        #     # Most restrictive wins (highest _rank)
        #     best = max(simulated_licenses, key=_rank)
        #     user_after[uname] = best

        # ── STEP 3: Compute AFTER state ────────────────────────────────────────
        # Strategy: start from BEFORE, only re-evaluate users who have at least
        # one reducible role. For those users, re-derive from ALL their role
        # licenses (with overrides applied). Everyone else stays unchanged.

        reducible_role_set = set(reducible_roles.keys())

        # Find only users who have at least one reducible role
        affected_users = {
            uname
            for uname, roles in user_roles.items()
            if any(role_name in reducible_role_set for (role_name, _) in roles)
        }

        logger.info(f"[{request_id}] Users with at least one reducible role: {len(affected_users)}")

        user_after: Dict[str, str] = {}

        for uname, before_lic in user_before.items():
            if uname not in affected_users:
                # No reducible roles — license cannot change
                user_after[uname] = before_lic
                continue

            roles = user_roles.get(uname, [])
            if not roles:
                user_after[uname] = before_lic
                continue

            # Re-evaluate with overrides applied
            simulated_licenses = []
            for (role_name, role_lic) in roles:
                if role_name in reducible_roles:
                    simulated_licenses.append(reducible_roles[role_name])
                else:
                    simulated_licenses.append(role_lic)

            best = max(simulated_licenses, key=_rank)
            user_after[uname] = best


        # ── STEP 4: Re-apply locked+expired override to AFTER state ───────────
        # Users who were NC in BEFORE due to locked+expired stay NC in AFTER.
        # We detect this by checking if their BEFORE license is NC AND they have
        # no roles (or all roles are NC) — simplest proxy is: if they were NC
        # before and none of their roles are in reducible_roles, keep NC.
        # But more correctly: honour UserLicSummary's CLEANUP_CATEGORY.
        for row in summary_rows:
            cleanup = getattr(row, 'CLEANUP_CATEGORY', None)
            if cleanup == 'Expired & Locked':
                # These are NC regardless of role changes
                user_after[row.UNAME] = "Not Classified"

        logger.info(f"[{request_id}] AFTER licenses computed for {len(user_after)} users")

        # ── STEP 5: Count tiers and compute FUE ───────────────────────────────
        def _count_tiers(user_lic_map: Dict[str, str]):
            gb = gc = gd = nc = 0
            for lic in user_lic_map.values():
                ll = (lic or "").lower()
                if "gb" in ll or "advanced" in ll:   gb += 1
                elif "gc" in ll or "core" in ll:     gc += 1
                elif "gd" in ll or "self" in ll:     gd += 1
                else:                                nc += 1

            total_fue = (
                math.ceil(gb  * FUE_FACTORS["GB Advanced Use"])
                + math.ceil(gc * FUE_FACTORS["GC Core Use"])
                + math.ceil(gd * FUE_FACTORS["GD Self-Service Use"])
            )
            return gb, gc, gd, nc, total_fue

        b_gb, b_gc, b_gd, b_nc, b_fue = _count_tiers(user_before)
        a_gb, a_gc, a_gd, a_nc, a_fue = _count_tiers(user_after)
        fue_saved      = b_fue - a_fue
        users_impacted = sum(1 for u in user_before if user_before[u] != user_after.get(u))

        logger.info(f"[{request_id}] BEFORE → GB={b_gb} GC={b_gc} GD={b_gd} NC={b_nc} FUE={b_fue}")
        logger.info(f"[{request_id}] AFTER  → GB={a_gb} GC={a_gc} GD={a_gd} NC={a_nc} FUE={a_fue}")
        logger.info(f"[{request_id}] FUE saved={fue_saved}, Users impacted={users_impacted}")

        sim_row = opt_sim_result_model(
            REQUEST_ID           = request_id,
            SYSTEM_NAME          = system_name,
            REDUCIBLE_ROLES      = ", ".join(sorted(reducible_roles.keys())),
            REDUCIBLE_ROLE_COUNT = len(reducible_roles),
            BEFORE_GB_USERS      = b_gb,
            BEFORE_GC_USERS      = b_gc,
            BEFORE_GD_USERS      = b_gd,
            BEFORE_NC_USERS      = b_nc,
            BEFORE_TOTAL_FUE     = b_fue,
            AFTER_GB_USERS       = a_gb,
            AFTER_GC_USERS       = a_gc,
            AFTER_GD_USERS       = a_gd,
            AFTER_NC_USERS       = a_nc,
            AFTER_TOTAL_FUE      = a_fue,
            FUE_SAVED            = fue_saved,
            USERS_IMPACTED       = users_impacted,
        )
        db.add(sim_row)
        db.commit()
        logger.info(f"[{request_id}] OptSimResult committed.")

    except Exception as exc:
        logger.error(f"[{request_id}] simulate_system_fue() failed: {exc}", exc_info=True)
        db.rollback()


# ---------------------------------------------------------------------------
# 5. Read helpers
# ---------------------------------------------------------------------------
async def get_all_requests_service(db: Session) -> List[RequestArray]:
    try:
        return db.query(RequestArray).order_by(RequestArray.TIMESTAMP.desc()).all()
    except Exception as exc:
        logger.error(f"get_all_requests_service failed: {exc}", exc_info=True)
        raise


async def get_distinct_license_types_service(
    db: Session, system_name: str
) -> List[Dict[str, str]]:
    try:
        RoleLicSummary = create_role_lic_summary_model(system_name)
        inspector = sqla_inspect(engine)
        if not inspector.has_table(RoleLicSummary.__tablename__):
            logger.warning(f"RoleLicSummary table '{RoleLicSummary.__tablename__}' not found.")
            return []
        rows = db.query(RoleLicSummary.CLASSIFY_LIC).distinct().all()
        return [{"id": r[0], "name": r[0]} for r in rows if r[0]]
    except Exception as exc:
        logger.error(f"get_distinct_license_types_service failed: {exc}", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _write_output_file(system_name: str, request_id: str, data: Dict) -> None:
    try:
        ts       = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{system_name}-{request_id}-{ts}.json"
        os.makedirs("output", exist_ok=True)
        with open(os.path.join("output", filename), "w") as fh:
            json.dump(data, fh, indent=4)
        logger.info(f"Output snapshot → output/{filename}")
    except Exception as exc:
        logger.error(f"Failed to write output file: {exc}", exc_info=True)