#
#
# import os
# from pathlib import Path
# from openai import OpenAI
# from anthropic import Anthropic
# from dotenv import load_dotenv
#
# from app.core.logger import setup_logger, get_daily_log_filename
#
# logger = setup_logger("app_logger")
# dotenv_path = Path('./env')
# load_dotenv()
#
# # 1 = ChatGPT, 2 = Claude
# AI_PROVIDER = 2
#
# openai_client = OpenAI()
# anthropic_client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
# def call_ai_api(prompt: str) -> str:
#     logger.info(f"Initiating AI call with prompt (first 100 chars): '{prompt[:100]}...'")
#     try:
#         if AI_PROVIDER == 1:
#             model_name = "gpt-4o-mini"
#             logger.info(f"Calling AI: ChatGPT model '{model_name}'")
#             return call_chatgpt_api(prompt)
#         elif AI_PROVIDER == 2:
#             model_name = "claude-opus-4-20250514"
#             logger.info(f"Calling AI: Claude model '{model_name}'")
#             return call_claude_api(prompt)
#         else:
#             logger.error(f"Error: Invalid AI_PROVIDER value ({AI_PROVIDER}). Use 1 for ChatGPT or 2 for Claude.")
#             return "Error: Invalid AI_PROVIDER value. Use 1 for ChatGPT or 2 for Claude."
#     except Exception as e:
#         error_message = f"Error calling AI API (provider {AI_PROVIDER}): {e}"
#         print(error_message)
#         logger.error(error_message)
#         return error_message
#
#
#
# def call_chatgpt_api(prompt: str) -> str:
#     logger.debug(f"Calling OpenAI API with model gpt-4o-mini and temperature=0.3")
#     try:
#         response = openai_client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[
#                 {"role": "system", "content": "You are an SAP license optimization assistant."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.3,
#             timeout=600
#         )
#         if response.choices:
#             content = response.choices[0].message.content.strip()
#             logger.info(f"Successfully received response from ChatGPT API. Response length: {len(content)}")
#             logger.debug(f"Full response content: '{content}'")
#             return response.choices[0].message.content.strip()
#         else:
#             logger.warning("OpenAI API returned a successful response, but without any choices.")
#             return "Error: No response from OpenAI API."
#
#     except Exception as e:
#         error_message = f"Error calling OpenAI API: {e}"
#         print(error_message)
#         logger.error(error_message, exc_info=True)
#         return error_message
#
#
# def call_claude_api(prompt: str) -> str:
#     """Call Claude API"""
#     logger.debug(f"Calling Anthropic API with model claude-opus-4-20250514 and max_tokens=4000")
#
#     try:
#         response = anthropic_client.messages.create(
#             # model="claude-3-5-sonnet-20241022",
#             # model="claude-opus-4-20250514",
#             model="claude-opus-4-20250514",
#             max_tokens=4000,
#             temperature=0.3,
#             system="You are an SAP license optimization assistant.",
#             messages=[
#                 {"role": "user", "content": prompt}
#             ]
#         )
#
#         if response.content:
#             content = response.content[0].text.strip()
#             logger.info(f"Successfully received response from Claude API. Response length: {len(content)}")
#             logger.debug(f"Full response content: '{content}'")
#             return response.content[0].text.strip()
#         else:
#             logger.warning("Anthropic API returned a successful response, but without any content.")
#             return "Error: No response from Claude API."
#
#     except Exception as e:
#         error_message = f"Error calling Claude API: {e}"
#         print(error_message)
#         logger.error(error_message, exc_info=True)
#         return error_message
#
#
# def call_chatgpt_api_legacy(prompt: str) -> str:
#     """Legacy function for backward compatibility"""
#     logger.warning("Using deprecated function 'call_chatgpt_api_legacy'. Consider updating calls to 'call_chatgpt_api'.")
#     return call_chatgpt_api(prompt)


import os
from pathlib import Path

from fastapi import requests
from openai import OpenAI
from anthropic import Anthropic
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app.core.logger import setup_logger, get_daily_log_filename
from app.models.database import SessionLocal
from app.models.ai_config import AIModelConfig

logger = setup_logger("app_logger")

load_dotenv()


openai_client = None
anthropic_client = None



def get_active_model_config() -> AIModelConfig:
    """Get the active AI model configuration from database"""
    db = SessionLocal()
    try:
        active_model = db.query(AIModelConfig).filter(
            AIModelConfig.is_active == True
        ).first()

        if not active_model:
            logger.error("No active AI model configured!")
            raise ValueError("No active AI model configured. Please set an active model in AI Settings.")

        return active_model
    finally:
        db.close()


def call_ai_api(prompt: str) -> str:
    """
    Main AI API caller - uses the active model from database configuration.
    """
    logger.info(f"Initiating AI call with prompt (first 100 chars): '{prompt[:100]}...'")

    try:
        # Get active model configuration
        config = get_active_model_config()

        logger.info(
            f"Using AI Model: {config.model_provider}/{config.model_name} "
            f"(max_tokens={config.max_tokens}, temperature={config.temperature})"
        )

        # Route to appropriate provider
        if config.model_provider == "anthropic":
            return call_claude_api(
                prompt=prompt,
                model=config.model_name,
                max_tokens=config.max_tokens,
                temperature=float(config.temperature)
            )

        elif config.model_provider == "openai":
            return call_openai_api(
                prompt=prompt,
                model=config.model_name,
                max_tokens=config.max_tokens,
                temperature=float(config.temperature)
            )

        elif config.model_provider == "ollama":  # ✅ Clean, separate routing logic
            return call_ollama_api(
                prompt=prompt,
                model=config.model_name,
                max_tokens=config.max_tokens,
                temperature=float(config.temperature)
            )

        else:
            error_msg = f"Unsupported AI provider: {config.model_provider}"
            logger.error(error_msg)
            return f"Error: {error_msg}"

    except Exception as e:
        error_message = f"Error calling AI API: {e}"
        logger.error(error_message, exc_info=True)
        return error_message

        # elif config.model_provider == "openai":
        #     return call_openai_api(
        #         prompt=prompt,
        #         model=config.model_name,
        #         max_tokens=config.max_tokens,
        #         temperature=float(config.temperature)
        #     )
        #
        # else:
        #     error_msg = f"Unsupported AI provider: {config.model_provider}"
        #     logger.error(error_msg)
        #     return f"Error: {error_msg}"

    except Exception as e:
        error_message = f"Error calling AI API: {e}"
        logger.error(error_message, exc_info=True)
        return error_message


def call_claude_api(
        prompt: str,
        model: str = "claude-opus-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.7
) -> str:
    """Call Claude API with specified configuration"""
    global anthropic_client

    logger.debug(f"Calling Anthropic API with model={model}, max_tokens={max_tokens}, temperature={temperature}")

    try:
        # Initialize client if needed
        if anthropic_client is None:
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not found in environment")
            anthropic_client = Anthropic(api_key=api_key)

        response = anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system="You are an SAP license optimization assistant.",
            messages=[{"role": "user", "content": prompt}]
        )

        if response.content:
            content = response.content[0].text.strip()
            logger.info(f"Successfully received response from Claude API. Response length: {len(content)}")
            logger.debug(f"Full response content: '{content[:500]}...'")
            return content
        else:
            logger.warning("Anthropic API returned empty response")
            return "Error: No response from Claude API."

    except Exception as e:
        error_message = f"Error calling Claude API: {e}"
        logger.error(error_message, exc_info=True)
        return error_message


def call_openai_api(
        prompt: str,
        model: str = "gpt-4o-mini",
        max_tokens: int = 4096,
        temperature: float = 0.3
) -> str:
    """Call OpenAI API with specified configuration"""
    global openai_client

    logger.debug(f"Calling OpenAI API with model={model}, max_tokens={max_tokens}, temperature={temperature}")

    try:
        # Initialize client if needed
        if openai_client is None:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment")
            openai_client = OpenAI(api_key=api_key)

        response = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an SAP license optimization assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=600
        )

        if response.choices:
            content = response.choices[0].message.content.strip()
            logger.info(f"Successfully received response from OpenAI API. Response length: {len(content)}")
            logger.debug(f"Full response content: '{content[:500]}...'")
            return content
        else:
            logger.warning("OpenAI API returned empty response")
            return "Error: No response from OpenAI API."

    except Exception as e:
        error_message = f"Error calling OpenAI API: {e}"
        logger.error(error_message, exc_info=True)
        return error_message


def call_ollama_api(
        prompt: str,
        model: str,
        max_tokens: int = 4096,
        temperature: float = 0.7
) -> str:
    """Call local Ollama API using its native endpoints"""
    logger.debug(f"Calling local Ollama service with model={model}, max_tokens={max_tokens}, temperature={temperature}")

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    url = f"{base_url}/api/generate"

    # Map your configurations to Ollama's standard native payload structure
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "system": "You are an SAP license optimization assistant.",
        "options": {
            "num_predict": max_tokens,
            "temperature": temperature
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=300)

        if response.status_code == 404:
            return f"Error: Model '{model}' not found in Ollama. Run 'ollama run {model}' in your terminal first."

        response.raise_for_status()
        result_json = response.json()

        content = result_json.get("response", "").strip()
        logger.info(f"Successfully received response from local Ollama. Length: {len(content)}")
        return content

    except requests.exceptions.ConnectionError:
        error_msg = f"Failed to connect to Ollama. Ensure 'ollama serve' is running at {base_url}"
        logger.error(error_msg)
        return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Error calling local Ollama API: {e}"
        logger.error(error_msg, exc_info=True)
        return f"Error: {error_msg}"

