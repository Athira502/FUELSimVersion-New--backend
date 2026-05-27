# from __future__ import annotations
#
# import json
# import os
# import datetime
# from collections import defaultdict
# from typing import Any, Dict, List, Optional, Set, Tuple
#
# from sqlalchemy import inspect as sqla_inspect
# from sqlalchemy.orm import Session
#
# from app.core.logger import setup_logger
# from app.models.database import engine, SessionLocal
# from app.models.dynamic_models import (
#     create_AGR1251_model,
#     create_AGRUSERS_model,
#     create_AGRDEFINE_model,
#     create_FLPCA_model,
#     create_role_lic_model,
#     create_role_lic_summary_model,
# )
# from app.models.request_array import RequestArray
# from app.models.Opt_results import (
#     LicenseOptimizationResult,
#     create_opt_sim_result_model,
# )
# from app.service.chatgpt import call_ai_api
#
# logger = setup_logger("app_logger")
#
#
# # ---------------------------------------------------------------------------
# # License tier ordering  (higher index = more restrictive = higher FUE cost)
# # ---------------------------------------------------------------------------
# _LICENSE_RANK: Dict[str, int] = {
#     "GD Self-Service Use": 1,
#     "GC Core Use":         2,
#     "GB Advanced Use":     3,
#     "Not Classified":      0,
# }
#
# _FUE_WEIGHT: Dict[str, float] = {
#     "GB Advanced Use":     1.00,
#     "GC Core Use":         0.50,
#     "GD Self-Service Use": 0.25,
#     "Not Classified":      0.00,
# }
#
#
# def _rank(license_name: Optional[str]) -> int:
#     """Returns the restrictiveness rank of a license string (higher = more restrictive)."""
#     if not license_name:
#         return 0
#     for key, rank in _LICENSE_RANK.items():
#         if key.lower() in license_name.lower():
#             return rank
#     return 3   # unknown → assume most restrictive
#
#
# def _weight(license_name: Optional[str]) -> float:
#     """Returns the FUE weight for a license string."""
#     if not license_name:
#         return 0.0
#     for key, w in _FUE_WEIGHT.items():
#         if key.lower() in license_name.lower():
#             return w
#     return 1.0   # unknown → assume highest cost
#
#
# def _most_restrictive(licenses: List[Optional[str]]) -> str:
#     """Returns the most restrictive license from a list."""
#     best = "Not Classified"
#     best_rank = 0
#     for lic in licenses:
#         if lic and _rank(lic) > best_rank:
#             best_rank = _rank(lic)
#             best = lic
#     return best
#
#
# # ---------------------------------------------------------------------------
# # Ensure a table exists
# # ---------------------------------------------------------------------------
# def _ensure_table(model_class) -> None:
#     inspector = sqla_inspect(engine)
#     if not inspector.has_table(model_class.__tablename__):
#         logger.info(f"Creating table '{model_class.__tablename__}'")
#         model_class.__table__.create(bind=engine)
#
#
# # ---------------------------------------------------------------------------
# # 1. Create request record immediately
# # ---------------------------------------------------------------------------
# async def create_optimization_request_immediately(
#     db: Session,
#     system_name: str,
# ) -> str:
#     """Inserts an IN_PROGRESS request row and returns req_id."""
#     logger.info(f"Creating optimisation request for system='{system_name}'.")
#
#     _ensure_table(RequestArray)
#     _ensure_table(LicenseOptimizationResult)
#
#     # Sequential ID: REQ100000, REQ100001, …
#     latest = (
#         db.query(RequestArray)
#         .filter(RequestArray.req_id.like("REQ%"))
#         .order_by(RequestArray.req_id.desc())
#         .first()
#     )
#     if latest and latest.req_id.startswith("REQ"):
#         try:
#             next_num = int(latest.req_id[3:]) + 1
#         except ValueError:
#             next_num = 100000
#     else:
#         next_num = 100000
#
#     req_id = f"REQ{next_num}"
#     db.add(RequestArray(req_id=req_id, SYSTEM_NAME=system_name, STATUS="IN_PROGRESS"))
#     db.commit()
#     logger.info(f"Request record '{req_id}' committed.")
#     return req_id
#
#
# # ---------------------------------------------------------------------------
# # 2. Background entry-point
# # ---------------------------------------------------------------------------
# def process_optimization_in_background(
#     system_name: str,
#     request_id: str,
#     target_license: str,
#     sap_system_info: str,
#     role_names: Optional[List[str]],
#     ratio_threshold: Optional[int],
# ) -> None:
#     """FastAPI BackgroundTasks entry-point — owns its own DB session."""
#     db = SessionLocal()
#     status = "FAILED"
#     try:
#         logger.info(f"[{request_id}] Background optimisation started.")
#         result = run_optimization_processing(
#             db=db,
#             system_name=system_name,
#             request_id=request_id,
#             target_license=target_license,
#             sap_system_info=sap_system_info,
#             role_names=role_names,
#             ratio_threshold=ratio_threshold,
#         )
#         status = "FAILED" if isinstance(result, dict) and "error" in result else "COMPLETED"
#         logger.info(f"[{request_id}] Processing finished → STATUS={status}")
#     except Exception as exc:
#         logger.error(f"[{request_id}] Unhandled background exception: {exc}", exc_info=True)
#     finally:
#         try:
#             req_row = db.query(RequestArray).filter(RequestArray.req_id == request_id).first()
#             if req_row:
#                 req_row.STATUS = status
#                 db.commit()
#         except Exception as upd_exc:
#             logger.error(f"[{request_id}] Failed to update status: {upd_exc}", exc_info=True)
#         db.close()
#
#
# # ---------------------------------------------------------------------------
# # 3. Core processing logic
# # ---------------------------------------------------------------------------
# def run_optimization_processing(
#     db: Session,
#     system_name: str,
#     request_id: str,
#     target_license: str,
#     sap_system_info: str,
#     role_names: Optional[List[str]],
#     ratio_threshold: Optional[int],
# ) -> Dict[str, Any]:
#
#     logger.info(
#         f"[{request_id}] run_optimization_processing() — "
#         f"system={system_name}, target_license={target_license}, roles={role_names or 'ALL'}"
#     )
#
#     inspector = sqla_inspect(engine)
#
#     # ---- Resolve dynamic models ----
#     RoleLic        = create_role_lic_model(system_name)
#     RoleLicSummary = create_role_lic_summary_model(system_name)
#     AGR1251        = create_AGR1251_model(system_name)
#     AGRUsers       = create_AGRUSERS_model(system_name)
#     AGRDefine      = create_AGRDEFINE_model(system_name)
#     OptSimResult   = create_opt_sim_result_model(system_name)
#     _ensure_table(OptSimResult)
#
#     # ---- Validate required tables ----
#     for model, label in [
#         (RoleLic,        "RoleLic"),
#         (RoleLicSummary, "RoleLicSummary"),
#         (AGR1251,        "AGR1251"),
#         (AGRUsers,       "AGRUsers"),
#     ]:
#         if not inspector.has_table(model.__tablename__):
#             msg = f"Required table '{model.__tablename__}' ({label}) not found. Load data first."
#             logger.error(f"[{request_id}] {msg}")
#             return {"error": msg, "status_code": 404}
#
#     has_agrdefine = inspector.has_table(AGRDefine.__tablename__)
#     if not has_agrdefine:
#         logger.warning(f"[{request_id}] AGRDEFINE table missing — role descriptions will be empty.")
#
#     # Optional FLPCA (Fiori)
#     FLPCAModel = None
#     try:
#         FLPCAModel = create_FLPCA_model(system_name)
#         if not inspector.has_table(FLPCAModel.__tablename__):
#             FLPCAModel = None
#     except Exception:
#         FLPCAModel = None
#     if not FLPCAModel:
#         logger.warning(f"[{request_id}] FLPCA table missing — Fiori data omitted.")
#
#     # ---- Query RoleLic rows for the target license ----
#     query = db.query(RoleLic).filter(RoleLic.CLASSIFY_LIC == target_license)
#     if role_names:
#         query = query.filter(RoleLic.AGR_NAME.in_(role_names))
#     roles_data = query.all()
#     logger.info(f"[{request_id}] RoleLic rows fetched: {len(roles_data)}")
#
#     if not roles_data:
#         msg = (
#             f"No roles found with license '{target_license}' for system '{system_name}'"
#             + (f" and roles {role_names}" if role_names else "")
#         )
#         logger.info(f"[{request_id}] {msg}")
#         return {"message": msg, "status_code": 404}
#
#     distinct_roles: List[str] = sorted({r.AGR_NAME for r in roles_data})
#     logger.info(f"[{request_id}] Distinct roles to analyse: {distinct_roles}")
#
#     # ---- Role descriptions from AGRDEFINE ----
#     role_descriptions: Dict[str, str] = {}
#     if has_agrdefine:
#         for row in db.query(AGRDefine).filter(AGRDefine.AGR_NAME.in_(distinct_roles)).all():
#             if row.AGR_NAME and row.TEXT:
#                 role_descriptions[row.AGR_NAME] = row.TEXT
#
#     # ---- Build per-role JSON payload for AI ----
#     all_roles_json: List[Dict] = []
#     for role in distinct_roles:
#         role_rows = [r for r in roles_data if r.AGR_NAME == role]
#         if not role_rows:
#             continue
#
#         auth_objects = [
#             {"object": r.OBJECT, "field": r.FIELD, "value": r.LOW}
#             for r in role_rows
#         ]
#
#         # Transaction codes from AGR1251 S_TCODE
#         tcodes = (
#             db.query(AGR1251.FIELD)
#             .filter(AGR1251.AGR_NAME == role, AGR1251.OBJECT == "S_TCODE", AGR1251.FIELD == "TCD")
#             .distinct().all()
#         )
#
#         # Fiori apps
#         fiori_apps: List[Dict] = []
#         if FLPCAModel:
#             try:
#                 seen: Dict[str, Dict] = {}
#                 for fr in db.query(FLPCAModel).filter(FLPCAModel.Single_Role_Name == role).all():
#                     app = fr.Title_Subtitle_Information
#                     act = fr.Semantic_Object_Action
#                     if app and app.strip():
#                         if app not in seen:
#                             seen[app] = {"app": app, "actions": []}
#                         if act and act.strip() and act not in seen[app]["actions"]:
#                             seen[app]["actions"].append(act)
#                 fiori_apps = list(seen.values())
#             except Exception as fe:
#                 logger.warning(f"[{request_id}] Fiori fetch failed for '{role}': {fe}")
#
#         all_roles_json.append({
#             "role":                 role,
#             "roleDescription":      role_descriptions.get(role, "No description available"),
#             "currentLicense":       target_license,
#             "authorizationObjects": auth_objects,
#             "transactionCodes":     sorted([t.FIELD for t in tcodes]),
#             "fioriApps":            fiori_apps,
#         })
#
#     logger.info(f"[{request_id}] Roles packaged for AI: {len(all_roles_json)}")
#     if not all_roles_json:
#         return {"message": "No role data to send to AI.", "status_code": 404}
#
#     # ---- Build AI prompt ----
#     prompt = f"""You are an SAP FUE licence optimisation expert.
# System: {system_name}
# SAP Info: {sap_system_info}
#
# The {len(all_roles_json)} role(s) below are currently classified as "{target_license}".
# For EACH role, decide if the overall role licence can be reduced, and provide:
#   1. A role-level licence suggestion (suggestedRoleLicense).
#   2. Per auth-object analysis.
#
# Role data:
# {json.dumps(all_roles_json, indent=2)}
#
# Return ONLY a valid JSON array — no markdown, no preamble — in EXACTLY this structure:
# [
#   {{
#     "role": "<AGR_NAME>",
#     "suggestedRoleLicense": "<GB Advanced Use | GC Core Use | GD Self-Service Use | No Change>",
#     "objects": [
#       {{
#         "authorizationObject": "<OBJECT>",
#         "field":               "<FIELD>",
#         "value":               "<VALUE>",
#         "licenseCanBeReduced": "Yes | No | May Be",
#
#         "insights":            "<short reason>",
#         "recommendation":      "<short action>",
#         "explanation":         "<detailed analysis>"
#       }}
#     ]
#   }}
# ]
# """
#
#     logger.info(f"[{request_id}] Sending prompt to AI (length={len(prompt)}).")
#     try:
#         ai_raw = call_ai_api(prompt)
#         logger.debug(f"[{request_id}] AI raw (first 500): {ai_raw[:500]}")
#     except Exception as ai_exc:
#         logger.error(f"[{request_id}] AI call failed: {ai_exc}", exc_info=True)
#         return {"error": f"AI API call failed: {ai_exc}", "status_code": 502}
#
#     # Strip markdown fences
#     ai_clean = ai_raw.strip()
#     for fence in ("```json", "```"):
#         if ai_clean.startswith(fence):
#             ai_clean = ai_clean[len(fence):]
#             break
#     if ai_clean.endswith("```"):
#         ai_clean = ai_clean[:-3]
#     ai_clean = ai_clean.strip()
#
#     try:
#         ai_roles: List[Dict] = json.loads(ai_clean)
#         logger.info(f"[{request_id}] AI returned {len(ai_roles)} role block(s).")
#     except json.JSONDecodeError as je:
#         logger.error(f"[{request_id}] JSON parse failed: {je}\nRaw:\n{ai_raw[:1000]}")
#         return {"error": f"Failed to parse AI response: {je}", "status_code": 502}
#
#     # ---- Write LicenseOptimizationResult rows + collect reducibility ----
#     # reducible_roles: {role_name: suggested_license}
#     # A role is reducible if NOT every object item is 'No'.
#     reducible_roles: Dict[str, str] = {}
#     results_by_role: Dict[str, List[Dict]] = {}
#
#     for role_block in ai_roles:
#         role_name          = role_block.get("role", "")
#         suggested_role_lic = role_block.get("suggestedRoleLicense", "")
#         objects            = role_block.get("objects", [])
#
#         if not role_name:
#             logger.warning(f"[{request_id}] AI block missing 'role' — skipping.")
#             continue
#
#         desc = role_descriptions.get(role_name, "No description available")
#
#         # Determine reducibility: ALL objects must be "Yes" or "May Be".
#         # A single "No" anywhere makes the role non-reducible.
#         statuses = [obj.get("licenseCanBeReduced", "No").strip().lower() for obj in objects]
#         all_yes_or_maybe = all(s in ("yes", "may be") for s in statuses)
#         is_reducible = all_yes_or_maybe and bool(suggested_role_lic) and suggested_role_lic != "No Change"
#
#         if is_reducible:
#             reducible_roles[role_name] = suggested_role_lic
#             logger.info(f"[{request_id}] Role '{role_name}' → REDUCIBLE → '{suggested_role_lic}'")
#         else:
#             logger.info(f"[{request_id}] Role '{role_name}' → NOT reducible")
#
#         # Write one row per auth-object
#         for obj in objects:
#             db_row = LicenseOptimizationResult(
#                 REQ_ID                 = request_id,
#                 ROLE_ID                = role_name,
#                 ROLE_DESCRIPTION       = desc,
#                 AUTHORIZATION_OBJECT   = obj.get("authorizationObject", ""),
#                 FIELD                  = obj.get("field", ""),
#                 VALUE                  = obj.get("value", ""),
#                 LICENSE_REDUCIBLE      = obj.get("licenseCanBeReduced", ""),
#                 SUGGESTED_ROLE_LICENSE = suggested_role_lic,
#                 INSIGHTS               = obj.get("insights", ""),
#                 RECOMMENDATIONS        = obj.get("recommendation", ""),
#                 EXPLANATIONS           = obj.get("explanation", ""),
#             )
#             db.add(db_row)
#
#         results_by_role[role_name] = objects
#
#     db.commit()
#     logger.info(
#         f"[{request_id}] LicenseOptimizationResult committed. "
#         f"Reducible roles: {list(reducible_roles.keys())}"
#     )
#
#     # ---- Full-system FUE simulation ----
#     simulate_system_fue(
#         db=db,
#         system_name=system_name,
#         request_id=request_id,
#         reducible_roles=reducible_roles,       # {role: new_license}
#         agr_users_model=AGRUsers,
#         role_lic_summary_model=RoleLicSummary,
#         opt_sim_result_model=OptSimResult,
#     )
#
#     # ---- JSON snapshot ----
#     _write_output_file(system_name, request_id, results_by_role)
#
#     logger.info(f"[{request_id}] run_optimization_processing() complete.")
#     return results_by_role
#
#
# # ---------------------------------------------------------------------------
# # 4. Full-system FUE simulation
# # ---------------------------------------------------------------------------
# def simulate_system_fue(
#     db: Session,
#     system_name: str,
#     request_id: str,
#     reducible_roles: Dict[str, str],        # {role_name: ai_suggested_license}
#     agr_users_model,
#     role_lic_summary_model,
#     opt_sim_result_model,
# ) -> None:
#     """
#     Recalculates system-wide FUE before and after applying AI suggestions.
#
#     Algorithm
#     ---------
#     1. Load ALL (UNAME, AGR_NAME) pairs from AGRUSERS.
#     2. Load ALL role → CLASSIFY_LIC mappings from RoleLicSummary.
#     3. For reducible roles, override their license with the AI suggestion.
#     4. For each user, compute:
#          before_license = most restrictive across all user's roles (original licenses)
#          after_license  = most restrictive across all user's roles (with overrides applied)
#     5. Count users per tier before and after; compute FUE totals.
#     6. Write one OptSimResult summary row.
#     """
#     logger.info(
#         f"[{request_id}] simulate_system_fue() — "
#         f"{len(reducible_roles)} reducible role(s): {list(reducible_roles.keys())}"
#     )
#
#     try:
#         # ---- Step 1: All user-role pairs ----
#         all_user_role_rows = db.query(
#             agr_users_model.UNAME,
#             agr_users_model.AGR_NAME,
#         ).all()
#         logger.info(f"[{request_id}] Total AGRUSERS rows: {len(all_user_role_rows)}")
#
#         # Build: {role_name: [user1, user2, …]}
#         role_to_users: Dict[str, Set[str]] = defaultdict(set)
#         all_users: Set[str] = set()
#         for row in all_user_role_rows:
#             if row.UNAME and row.AGR_NAME:
#                 role_to_users[row.AGR_NAME].add(row.UNAME)
#                 all_users.add(row.UNAME)
#
#         logger.info(f"[{request_id}] Unique users in system: {len(all_users)}")
#         logger.info(f"[{request_id}] Unique roles in system: {len(role_to_users)}")
#
#         # ---- Step 2: Role → license mapping from RoleLicSummary ----
#         summary_rows = db.query(
#             role_lic_summary_model.AGR_NAME,
#             role_lic_summary_model.CLASSIFY_LIC,
#         ).all()
#
#         baseline_license: Dict[str, str] = {}   # {role: license}
#         for row in summary_rows:
#             if row.AGR_NAME:
#                 baseline_license[row.AGR_NAME] = row.CLASSIFY_LIC or "Not Classified"
#
#         logger.info(f"[{request_id}] RoleLicSummary rows loaded: {len(baseline_license)}")
#
#         # ---- Step 3: Build before/after license map per role ----
#         # before: baseline_license as-is
#         # after:  override reducible roles with AI suggestion
#         after_license: Dict[str, str] = dict(baseline_license)
#         for role, new_lic in reducible_roles.items():
#             after_license[role] = new_lic
#             logger.info(
#                 f"[{request_id}] License override: '{role}' "
#                 f"{baseline_license.get(role, 'Unknown')} → {new_lic}"
#             )
#
#         # ---- Step 4: Per-user most-restrictive license BEFORE and AFTER ----
#         # user_before[user] = most-restrictive license across all their roles (baseline)
#         # user_after[user]  = most-restrictive license after overrides
#         user_before: Dict[str, str] = {}
#         user_after:  Dict[str, str] = {}
#
#         for user in all_users:
#             user_before[user] = "Not Classified"
#             user_after[user]  = "Not Classified"
#
#         for role, users in role_to_users.items():
#             role_lic_before = baseline_license.get(role, "Not Classified")
#             role_lic_after  = after_license.get(role, "Not Classified")
#
#             for user in users:
#                 # Before
#                 if _rank(role_lic_before) > _rank(user_before.get(user, "Not Classified")):
#                     user_before[user] = role_lic_before
#                 # After
#                 if _rank(role_lic_after) > _rank(user_after.get(user, "Not Classified")):
#                     user_after[user] = role_lic_after
#
#         # ---- Step 5: Aggregate tier counts and FUE totals ----
#         def _count_tiers(user_lic_map: Dict[str, str]) -> Tuple[int, int, int, int, float]:
#             """Returns (GB, GC, GD, NC, total_FUE)."""
#             gb = gc = gd = nc = 0
#             total_fue = 0.0
#             for lic in user_lic_map.values():
#                 w = _weight(lic)
#                 total_fue += w
#                 lic_lower = (lic or "").lower()
#                 if "gb" in lic_lower or "advanced" in lic_lower:
#                     gb += 1
#                 elif "gc" in lic_lower or "core" in lic_lower:
#                     gc += 1
#                 elif "gd" in lic_lower or "self" in lic_lower:
#                     gd += 1
#                 else:
#                     nc += 1
#             return gb, gc, gd, nc, round(total_fue, 4)
#
#         b_gb, b_gc, b_gd, b_nc, b_fue = _count_tiers(user_before)
#         a_gb, a_gc, a_gd, a_nc, a_fue = _count_tiers(user_after)
#
#         fue_saved = round(b_fue - a_fue, 4)
#
#         # Users whose tier actually changed
#         users_impacted = sum(
#             1 for u in all_users if user_before.get(u) != user_after.get(u)
#         )
#
#         logger.info(
#             f"[{request_id}] BEFORE → GB={b_gb} GC={b_gc} GD={b_gd} NC={b_nc} FUE={b_fue}"
#         )
#         logger.info(
#             f"[{request_id}] AFTER  → GB={a_gb} GC={a_gc} GD={a_gd} NC={a_nc} FUE={a_fue}"
#         )
#         logger.info(
#             f"[{request_id}] FUE saved={fue_saved}, Users impacted={users_impacted}"
#         )
#
#         # ---- Step 6: Write summary row ----
#         sim_row = opt_sim_result_model(
#             REQUEST_ID           = request_id,
#             SYSTEM_NAME          = system_name,
#             REDUCIBLE_ROLES      = ", ".join(sorted(reducible_roles.keys())),
#             REDUCIBLE_ROLE_COUNT = len(reducible_roles),
#             BEFORE_GB_USERS      = b_gb,
#             BEFORE_GC_USERS      = b_gc,
#             BEFORE_GD_USERS      = b_gd,
#             BEFORE_NC_USERS      = b_nc,
#             BEFORE_TOTAL_FUE     = b_fue,
#             AFTER_GB_USERS       = a_gb,
#             AFTER_GC_USERS       = a_gc,
#             AFTER_GD_USERS       = a_gd,
#             AFTER_NC_USERS       = a_nc,
#             AFTER_TOTAL_FUE      = a_fue,
#             FUE_SAVED            = fue_saved,
#             USERS_IMPACTED       = users_impacted,
#         )
#         db.add(sim_row)
#         db.commit()
#         logger.info(f"[{request_id}] OptSimResult summary row committed.")
#
#     except Exception as exc:
#         logger.error(f"[{request_id}] simulate_system_fue() failed: {exc}", exc_info=True)
#         db.rollback()
#
#
# # ---------------------------------------------------------------------------
# # 5. Read helpers
# # ---------------------------------------------------------------------------
# async def get_all_requests_service(db: Session) -> List[RequestArray]:
#     try:
#         return db.query(RequestArray).order_by(RequestArray.TIMESTAMP.desc()).all()
#     except Exception as exc:
#         logger.error(f"get_all_requests_service failed: {exc}", exc_info=True)
#         raise
#
#
# async def get_distinct_license_types_service(
#     db: Session, system_name: str
# ) -> List[Dict[str, str]]:
#     try:
#         RoleLicSummary = create_role_lic_summary_model(system_name)
#         inspector = sqla_inspect(engine)
#         if not inspector.has_table(RoleLicSummary.__tablename__):
#             logger.warning(
#                 f"RoleLicSummary table '{RoleLicSummary.__tablename__}' not found."
#             )
#             return []
#         rows = db.query(RoleLicSummary.CLASSIFY_LIC).distinct().all()
#         return [{"id": r[0], "name": r[0]} for r in rows if r[0]]
#     except Exception as exc:
#         logger.error(f"get_distinct_license_types_service failed: {exc}", exc_info=True)
#         return []
#
#
# # ---------------------------------------------------------------------------
# # Internal helpers
# # ---------------------------------------------------------------------------
# def _write_output_file(system_name: str, request_id: str, data: Dict) -> None:
#     try:
#         ts       = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
#         filename = f"{system_name}-{request_id}-{ts}.json"
#         os.makedirs("output", exist_ok=True)
#         with open(os.path.join("output", filename), "w") as fh:
#             json.dump(data, fh, indent=4)
#         logger.info(f"Output snapshot → output/{filename}")
#     except Exception as exc:
#         logger.error(f"Failed to write output file: {exc}", exc_info=True)


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
from app.service.chatgpt import call_ai_api

logger = setup_logger("app_logger")

# ---------------------------------------------------------------------------
# License tier ordering  (higher index = more restrictive = higher FUE cost)
# ---------------------------------------------------------------------------
_LICENSE_RANK: Dict[str, int] = {
    "GD Self-Service Use": 1,
    "GC Core Use": 2,
    "GB Advanced Use": 3,
    "Not Classified": 0,
}

_FUE_WEIGHT: Dict[str, float] = {
    "GB Advanced Use": 1.00,
    "GC Core Use": 0.50,
    "GD Self-Service Use": 0.25,
    "Not Classified": 0.00,
}


def _rank(license_name: Optional[str]) -> int:
    """Returns the restrictiveness rank of a license string (higher = more restrictive)."""
    if not license_name:
        return 0
    for key, rank in _LICENSE_RANK.items():
        if key.lower() in license_name.lower():
            return rank
    return 3  # unknown → assume most restrictive


def _weight(license_name: Optional[str]) -> float:
    """Returns the FUE weight for a license string."""
    if not license_name:
        return 0.0
    for key, w in _FUE_WEIGHT.items():
        if key.lower() in license_name.lower():
            return w
    return 1.0  # unknown → assume highest cost


def _most_restrictive(licenses: List[Optional[str]]) -> str:
    """Returns the most restrictive license from a list."""
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
    """Fetch description for an authorization object from Z_FUE_{system}_OBJ_TEXT."""
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
    """
    Get distinct possible values for a specific object+field combination
    from the ruleset (RoleLic table).
    """
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
        logger.warning(
            f"Failed to get possible values for {auth_object}/{field}: {exc}"
        )
        return ""


# ---------------------------------------------------------------------------
# Helper: Get transaction code description
# ---------------------------------------------------------------------------
def _get_tcode_description(db: Session, system_name: str, tcode: str) -> str:
    """Fetch transaction code description from Z_FUE_{system}_TCODE_TEXT."""
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
# Helper: Build enhanced authorization objects with transaction code mapping
# ---------------------------------------------------------------------------
def _build_enhanced_auth_objects(
        db: Session,
        system_name: str,
        role: str,
        role_rows: List,
        role_tcodes: Set[str]
) -> List[Dict[str, Any]]:
    """
    Build authorization objects list with enhanced information:
    1. For manually added objects (OBJ_STATUS='U'): basic info + description + possible values
    2. For system-added objects: include relevant transaction codes that match role's tcodes
    """

    AGR1251 = create_AGR1251_model(system_name)
    USOBXCModel = create_USOBXC_model(system_name)

    # Get all AGR1251 rows for this role with OBJ_STATUS
    agr1251_rows = db.query(
        AGR1251.OBJECT,
        AGR1251.FIELD,
        AGR1251.LOW,
        AGR1251.OBJ_STATUS
    ).filter(AGR1251.AGR_NAME == role).all()

    # Build a map: (object, field, value) -> obj_status
    obj_status_map = {
        (row.OBJECT, row.FIELD, row.LOW): row.OBJ_STATUS
        for row in agr1251_rows
    }

    # Build enhanced objects list
    auth_objects = []
    processed_keys = set()  # Track (object, field, value) to avoid duplicates

    for r in role_rows:
        key = (r.OBJECT, r.FIELD, r.LOW)

        if key in processed_keys:
            continue
        processed_keys.add(key)

        obj_status = obj_status_map.get(key, '')

        # Get object description
        description = _get_object_description(db, system_name, r.OBJECT)

        # Get possible values from ruleset
        possible_values = _get_possible_values_from_ruleset(
            db, system_name, r.OBJECT, r.FIELD
        )

        auth_obj_dict = {
            "object": r.OBJECT,
            "field": r.FIELD,
            "value": r.LOW,
            "description": description,
            "possibleValues": possible_values,
        }

        # Check if manually added (OBJ_STATUS = 'U')
        if obj_status == 'U':
            # Manually added - no transaction code mapping needed
            auth_objects.append(auth_obj_dict)
            logger.debug(
                f"[{role}] Manual object: {r.OBJECT}/{r.FIELD}={r.LOW}"
            )
        else:
            # System-added - find relevant transaction codes
            try:
                # Query USOBXC for tcodes that propose this auth object
                usobxc_rows = db.query(USOBXCModel.NAME).filter(
                    USOBXCModel.AUTH_OBJ == r.OBJECT,
                    USOBXCModel.OKFLAG == 'Y',
                    USOBXCModel.PROPOSED_VALUE_FOR == 'TR'
                ).distinct().all()

                # Filter to only tcodes that exist in the role's tcode list
                relevant_tcodes = [
                    row.NAME for row in usobxc_rows
                    if row.NAME and row.NAME in role_tcodes
                ]

                if relevant_tcodes:
                    # Get descriptions for relevant tcodes
                    tcode_with_desc = []
                    for tcode in relevant_tcodes:
                        desc = _get_tcode_description(db, system_name, tcode)
                        if desc:
                            tcode_with_desc.append(f"{tcode} ({desc})")
                        else:
                            tcode_with_desc.append(tcode)

                    auth_obj_dict["relevantTransactionCodes"] = ", ".join(
                        sorted(tcode_with_desc)
                    )

                    logger.debug(
                        f"[{role}] System object: {r.OBJECT}/{r.FIELD}={r.LOW} "
                        f"→ {len(relevant_tcodes)} relevant tcodes"
                    )
                else:
                    # No relevant tcodes found, but still include the object
                    auth_obj_dict["relevantTransactionCodes"] = ""
                    logger.debug(
                        f"[{role}] System object: {r.OBJECT}/{r.FIELD}={r.LOW} "
                        f"→ no relevant tcodes"
                    )

            except Exception as exc:
                logger.warning(
                    f"[{role}] Failed to fetch USOBXC data for {r.OBJECT}: {exc}"
                )
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
    """
    Build transaction codes list with descriptions.
    Returns: [{"tcode": "SU01", "description": "User Maintenance"}, ...]
    """
    enhanced_tcodes = []

    for tcode in sorted(tcode_list):
        desc = _get_tcode_description(db, system_name, tcode)
        enhanced_tcodes.append({
            "tcode": tcode,
            "description": desc
        })

    return enhanced_tcodes


# ---------------------------------------------------------------------------
# 1. Create request record immediately
# ---------------------------------------------------------------------------
async def create_optimization_request_immediately(
        db: Session,
        system_name: str,
) -> str:
    """Inserts an IN_PROGRESS request row and returns req_id."""
    logger.info(f"Creating optimisation request for system='{system_name}'.")

    _ensure_table(RequestArray)
    _ensure_table(LicenseOptimizationResult)

    # Sequential ID: REQ100000, REQ100001, …
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
    """FastAPI BackgroundTasks entry-point — owns its own DB session."""
    db = SessionLocal()
    status = "FAILED"
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
        status = "FAILED" if isinstance(result, dict) and "error" in result else "COMPLETED"
        logger.info(f"[{request_id}] Processing finished → STATUS={status}")
    except Exception as exc:
        logger.error(f"[{request_id}] Unhandled background exception: {exc}", exc_info=True)
    finally:
        try:
            req_row = db.query(RequestArray).filter(RequestArray.req_id == request_id).first()
            if req_row:
                req_row.STATUS = status
                db.commit()
        except Exception as upd_exc:
            logger.error(f"[{request_id}] Failed to update status: {upd_exc}", exc_info=True)
        db.close()


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
    RoleLic = create_role_lic_model(system_name)
    RoleLicSummary = create_role_lic_summary_model(system_name)
    AGR1251 = create_AGR1251_model(system_name)
    AGRUsers = create_AGRUSERS_model(system_name)
    AGRDefine = create_AGRDEFINE_model(system_name)
    OptSimResult = create_opt_sim_result_model(system_name)
    _ensure_table(OptSimResult)

    # ---- Validate required tables ----
    for model, label in [
        (RoleLic, "RoleLic"),
        (RoleLicSummary, "RoleLicSummary"),
        (AGR1251, "AGR1251"),
        (AGRUsers, "AGRUsers"),
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

        # Step 1: Extract all transaction codes for this role
        tcodes_query = (
            db.query(AGR1251.LOW)
            .filter(
                AGR1251.AGR_NAME == role,
                AGR1251.OBJECT == "S_TCODE",
                AGR1251.FIELD == "TCD"
            )
            .distinct().all()
        )
        role_tcodes = {t.LOW for t in tcodes_query if t.LOW}
        logger.info(f"[{request_id}] Role '{role}' has {len(role_tcodes)} tcodes")

        # Step 2 & 3: Build enhanced authorization objects
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
            "role": role,
            "roleDescription": role_descriptions.get(role, "No description available"),
            "currentLicense": target_license,
            "authorizationObjects": auth_objects,
            "transactionCodes": enhanced_tcodes,
            "fioriApps": fiori_apps,
        })

    logger.info(f"[{request_id}] Roles packaged for AI: {len(all_roles_json)}")
    if not all_roles_json:
        return {"message": "No role data to send to AI.", "status_code": 404}

    # ---- Build AI prompt ----
    prompt = f"""You are an SAP FUE licence optimisation expert.
System: {system_name}
SAP Info: {sap_system_info}

The {len(all_roles_json)} role(s) below are currently classified as "{target_license}".
For EACH role, decide if the overall role licence can be reduced, and provide:
  1. A role-level licence suggestion (suggestedRoleLicense).
  2. Per auth-object analysis.

Role data:
{json.dumps(all_roles_json, indent=2)}

Each authorization object includes:
- object: Authorization object name
- field: Authorization field name
- value: Current value
- description: Object description
- possibleValues: Available values from the ruleset for this object/field combination
- relevantTransactionCodes: Transaction codes that use this authorization object (only for system-added objects)

Each transaction code includes:
- tcode: Transaction code
- description: Transaction description

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
        "explanation":         "<detailed analysis considering transaction codes and possible values>"
      }}
    ]
  }}
]
"""

    logger.info(f"[{request_id}] Sending prompt to AI (length={len(prompt)}).")
    logger.info(f"Prompt: {prompt}")
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

    try:
        ai_roles: List[Dict] = json.loads(ai_clean)
        logger.info(f"[{request_id}] AI returned {len(ai_roles)} role block(s).")
    except json.JSONDecodeError as je:
        logger.error(f"[{request_id}] JSON parse failed: {je}\nRaw:\n{ai_raw[:1000]}")
        return {"error": f"Failed to parse AI response: {je}", "status_code": 502}

    # ---- Write LicenseOptimizationResult rows + collect reducibility ----
    reducible_roles: Dict[str, str] = {}
    results_by_role: Dict[str, List[Dict]] = {}

    for role_block in ai_roles:
        role_name = role_block.get("role", "")
        suggested_role_lic = role_block.get("suggestedRoleLicense", "")
        objects = role_block.get("objects", [])

        if not role_name:
            logger.warning(f"[{request_id}] AI block missing 'role' — skipping.")
            continue

        desc = role_descriptions.get(role_name, "No description available")

        # Determine reducibility: ALL objects must be "Yes" or "May Be"
        statuses = [obj.get("licenseCanBeReduced", "No").strip().lower() for obj in objects]
        all_yes_or_maybe = all(s in ("yes", "may be") for s in statuses)
        is_reducible = all_yes_or_maybe and bool(suggested_role_lic) and suggested_role_lic != "No Change"

        if is_reducible:
            reducible_roles[role_name] = suggested_role_lic
            logger.info(f"[{request_id}] Role '{role_name}' → REDUCIBLE → '{suggested_role_lic}'")
        else:
            logger.info(f"[{request_id}] Role '{role_name}' → NOT reducible")

        # Write one row per auth-object
        for obj in objects:
            db_row = LicenseOptimizationResult(
                REQ_ID=request_id,
                ROLE_ID=role_name,
                ROLE_DESCRIPTION=desc,
                AUTHORIZATION_OBJECT=obj.get("authorizationObject", ""),
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

    db.commit()
    logger.info(
        f"[{request_id}] LicenseOptimizationResult committed. "
        f"Reducible roles: {list(reducible_roles.keys())}"
    )

    # ---- Full-system FUE simulation ----
    simulate_system_fue(
        db=db,
        system_name=system_name,
        request_id=request_id,
        reducible_roles=reducible_roles,
        agr_users_model=AGRUsers,
        role_lic_summary_model=RoleLicSummary,
        opt_sim_result_model=OptSimResult,
    )

    # ---- JSON snapshot ----
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
    """
    Recalculates system-wide FUE before and after applying AI suggestions.
    """
    logger.info(
        f"[{request_id}] simulate_system_fue() — "
        f"{len(reducible_roles)} reducible role(s): {list(reducible_roles.keys())}"
    )

    try:
        # ---- Step 1: All user-role pairs ----
        all_user_role_rows = db.query(
            agr_users_model.UNAME,
            agr_users_model.AGR_NAME,
        ).all()
        logger.info(f"[{request_id}] Total AGRUSERS rows: {len(all_user_role_rows)}")

        # Build: {role_name: [user1, user2, …]}
        role_to_users: Dict[str, Set[str]] = defaultdict(set)
        all_users: Set[str] = set()
        for row in all_user_role_rows:
            if row.UNAME and row.AGR_NAME:
                role_to_users[row.AGR_NAME].add(row.UNAME)
                all_users.add(row.UNAME)

        logger.info(f"[{request_id}] Unique users in system: {len(all_users)}")
        logger.info(f"[{request_id}] Unique roles in system: {len(role_to_users)}")

        # ---- Step 2: Role → license mapping from RoleLicSummary ----
        summary_rows = db.query(
            role_lic_summary_model.AGR_NAME,
            role_lic_summary_model.CLASSIFY_LIC,
        ).all()

        baseline_license: Dict[str, str] = {}
        for row in summary_rows:
            if row.AGR_NAME:
                baseline_license[row.AGR_NAME] = row.CLASSIFY_LIC or "Not Classified"

        logger.info(f"[{request_id}] RoleLicSummary rows loaded: {len(baseline_license)}")

        # ---- Step 3: Build before/after license map per role ----
        after_license: Dict[str, str] = dict(baseline_license)
        for role, new_lic in reducible_roles.items():
            after_license[role] = new_lic
            logger.info(
                f"[{request_id}] License override: '{role}' "
                f"{baseline_license.get(role, 'Unknown')} → {new_lic}"
            )

        # ---- Step 4: Per-user most-restrictive license BEFORE and AFTER ----
        user_before: Dict[str, str] = {}
        user_after: Dict[str, str] = {}

        for user in all_users:
            user_before[user] = "Not Classified"
            user_after[user] = "Not Classified"

        for role, users in role_to_users.items():
            role_lic_before = baseline_license.get(role, "Not Classified")
            role_lic_after = after_license.get(role, "Not Classified")

            for user in users:
                # Before
                if _rank(role_lic_before) > _rank(user_before.get(user, "Not Classified")):
                    user_before[user] = role_lic_before
                # After
                if _rank(role_lic_after) > _rank(user_after.get(user, "Not Classified")):
                    user_after[user] = role_lic_after

        # ---- Step 5: Aggregate tier counts and FUE totals ----
        def _count_tiers(user_lic_map: Dict[str, str]) -> Tuple[int, int, int, int, float]:
            """Returns (GB, GC, GD, NC, total_FUE)."""
            gb = gc = gd = nc = 0
            total_fue = 0.0
            for lic in user_lic_map.values():
                w = _weight(lic)
                total_fue += w
                lic_lower = (lic or "").lower()
                if "gb" in lic_lower or "advanced" in lic_lower:
                    gb += 1
                elif "gc" in lic_lower or "core" in lic_lower:
                    gc += 1
                elif "gd" in lic_lower or "self" in lic_lower:
                    gd += 1
                else:
                    nc += 1
            return gb, gc, gd, nc, round(total_fue, 4)

        b_gb, b_gc, b_gd, b_nc, b_fue = _count_tiers(user_before)
        a_gb, a_gc, a_gd, a_nc, a_fue = _count_tiers(user_after)

        fue_saved = round(b_fue - a_fue, 4)

        # Users whose tier actually changed
        users_impacted = sum(
            1 for u in all_users if user_before.get(u) != user_after.get(u)
        )

        logger.info(
            f"[{request_id}] BEFORE → GB={b_gb} GC={b_gc} GD={b_gd} NC={b_nc} FUE={b_fue}"
        )
        logger.info(
            f"[{request_id}] AFTER  → GB={a_gb} GC={a_gc} GD={a_gd} NC={a_nc} FUE={a_fue}"
        )
        logger.info(
            f"[{request_id}] FUE saved={fue_saved}, Users impacted={users_impacted}"
        )

        # ---- Step 6: Write summary row ----
        sim_row = opt_sim_result_model(
            REQUEST_ID=request_id,
            SYSTEM_NAME=system_name,
            REDUCIBLE_ROLES=", ".join(sorted(reducible_roles.keys())),
            REDUCIBLE_ROLE_COUNT=len(reducible_roles),
            BEFORE_GB_USERS=b_gb,
            BEFORE_GC_USERS=b_gc,
            BEFORE_GD_USERS=b_gd,
            BEFORE_NC_USERS=b_nc,
            BEFORE_TOTAL_FUE=b_fue,
            AFTER_GB_USERS=a_gb,
            AFTER_GC_USERS=a_gc,
            AFTER_GD_USERS=a_gd,
            AFTER_NC_USERS=a_nc,
            AFTER_TOTAL_FUE=a_fue,
            FUE_SAVED=fue_saved,
            USERS_IMPACTED=users_impacted,
        )
        db.add(sim_row)
        db.commit()
        logger.info(f"[{request_id}] OptSimResult summary row committed.")

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
            logger.warning(
                f"RoleLicSummary table '{RoleLicSummary.__tablename__}' not found."
            )
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
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{system_name}-{request_id}-{ts}.json"
        os.makedirs("output", exist_ok=True)
        with open(os.path.join("output", filename), "w") as fh:
            json.dump(data, fh, indent=4)
        logger.info(f"Output snapshot → output/{filename}")
    except Exception as exc:
        logger.error(f"Failed to write output file: {exc}", exc_info=True)