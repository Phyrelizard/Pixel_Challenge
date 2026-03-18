from games.dot_dash import DotDashModule


def build_game_registry():
    modules = [
        DotDashModule(),
    ]
    return {module.META.key: module for module in modules}
