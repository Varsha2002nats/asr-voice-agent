"""
Utility functions for prompt generation.
"""

#from ..config.prompts import SYSTEM_MESSAGE_TEMPLATE
from ..config.prompts_simple import SYSTEM_MESSAGE_TEMPLATE


# def generate_system_message(caller_phone=None):
#     """
#     Generate the system message for OpenAI, including caller's phone if available.

#     Args:
#         caller_phone: The caller's phone number, if available

#     Returns:
#         str: The formatted system message
#     """
#     if caller_phone and caller_phone != "Unknown":
#         return SYSTEM_MESSAGE_TEMPLATE.replace("--caller_phone--", caller_phone)
#     else:
#         # Remove the caller information section if we don't have a valid phone number
#         return SYSTEM_MESSAGE_TEMPLATE.replace(
#             "\n\nCALLER INFORMATION:\n"
#             "- Phone Number: --caller_phone--\n"
#             "- If this number is provided, ask the caller if they would like to use this number for their order or provide a different one",
#             "",
#         )

def generate_system_message(caller_phone=None):
    """
    Returns the simplified test prompt that asks only for name and email.
    """
    return SYSTEM_MESSAGE_TEMPLATE
