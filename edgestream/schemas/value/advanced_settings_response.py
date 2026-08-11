from pydantic import BaseModel


class DuplicateAdvancedSettingsResponse(BaseModel):
    detail: str = "Advanced Setting with Label: {label} already exists"

class DeleteAdvancedSettingResponse(BaseModel):
    detail: str = "Advanced Setting with Label: {label} deleted."


class IncorrectAdvancedSettingResponse(BaseModel):
    detail: str = "Advanced Setting with Label: {label} not found."


get_advanced_settings_error_responses = {
    400: {
        "content": {
            "application/json": {
                "examples": {
                    "DuplicateAdvancedSettingsResponse": {
                        "value": {
                            "detail": "Advanced Setting with Label: {label} already exists"
                        }
                    },
                },
            }
        }
    }
}
