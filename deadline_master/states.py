from maxapi.context import StatesGroup, State

class Form(StatesGroup):
    name = State()
    date = State()