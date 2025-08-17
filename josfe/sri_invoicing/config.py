from josfe.josfe.doctype.fe_settings.fe_settings import get_settings  # re-export

__all__ = ["fe_get"]

def fe_get():
    """Public accessor used across signing/transmission/builders."""
    return get_settings()
