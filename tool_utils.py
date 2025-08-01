# /Users/abc/Downloads/Credflow/wall-e/app/agent/tool_utils.py
import json

from pydantic import BaseModel


def _normalise_inputs(*args, **kwargs) -> dict:
    """
    Turn every calling pattern LangChain might use into keyword args.
    Covers:
      • keyword args
      • positional order
      • single dict
      • single Pydantic model
      • single JSON string blob
    """
    if args:
        first = args[0]

        if isinstance(first, dict):
            kwargs.update(first)

        elif isinstance(first, BaseModel):
            kwargs.update(first.dict())

        elif isinstance(first, str) and first.lstrip().startswith("{"):
            try:
                kwargs.update(json.loads(first))
            except Exception:
                # Treat as positional pnl_json_list_str (Persist tool)
                kwargs.setdefault("pnl_json_list_str", first)

        else:  # plain positional order for Persist tool
            if "pnl_json_list_str" not in kwargs:
                kwargs["pnl_json_list_str"] = first
            if len(args) > 1:
                kwargs.setdefault("bs_json_list_str", args[1])
            if len(args) > 2:
                kwargs.setdefault("application_id", args[2])
            if len(args) > 3:
                kwargs.setdefault("company_gst", args[3])

    return kwargs
