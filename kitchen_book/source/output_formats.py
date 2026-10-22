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


def obj(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}
def text(limit):
    return {'type':'string','minLength':1,'maxLength':limit}
def array(item, lo, hi):
    return {'type':'array','items':item,'minItems':lo,'maxItems':hi}
MENUS = obj({'menus':array(obj({'name':text(40),'reason':text(70),'missing':array(text(30),0,8)}),3,3)})
RECIPE = obj({'title':text(60),'ingredients':array(text(60),1,15),
    'steps':array(obj({'title':text(30),'instruction':text(180),
        'timer_seconds':{'type':'integer','minimum':0,'maximum':86400}}),4,6),
    'notes':array(text(100),0,4)})
