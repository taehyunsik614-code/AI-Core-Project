"""JSON schemas passed to llama.cpp's constrained decoder for image responses."""
OBSERVATIONS = {
    'type': 'object',
    'properties': {
        'objects': {'type': 'array', 'maxItems': 12, 'items': {
            'type': 'object',
            'properties': {'name': {'type': 'string'}, 'evidence': {'type': 'string'}},
            'required': ['name', 'evidence'], 'additionalProperties': False}},
        'uncertain': {'type': 'array', 'maxItems': 20, 'items': {'type': 'string'}}},
    'required': ['objects', 'uncertain'], 'additionalProperties': False}


def checks(names):
    return {'type': 'object', 'properties': {'checks': {
        'type': 'array', 'minItems': len(names), 'maxItems': len(names),
        'items': {'type': 'object', 'properties': {
            'name': {'type': 'string', 'enum': names},
            'visible': {'type': 'boolean'}, 'evidence': {'type': 'string'}},
            'required': ['name', 'visible', 'evidence'], 'additionalProperties': False}}},
        'required': ['checks'], 'additionalProperties': False}

def string_list(limit):
    return {'type':'array','maxItems':limit,'items':{'type':'string'}}

def record(fields):
    return {'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}

QUICK_NAMES = record({'names':string_list(12)})
SHORT_STEP = record({'title':{'type':'string'}, 'instruction':{'type':'string'}})
SHORT_RECIPE = record({'ingredients':string_list(30),
                       'steps':{'type':'array','minItems':3,'maxItems':6,'items':SHORT_STEP}})
