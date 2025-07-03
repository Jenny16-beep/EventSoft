import base64
from django import template

register = template.Library()

@register.filter
def b64encode(value):
    if value:
        return base64.b64encode(value).decode('utf-8')
    return ''

@register.filter
def get(dictionary, key):
    return dictionary.get(key, 0)