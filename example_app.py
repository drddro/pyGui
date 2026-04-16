from core.gui.elements import UIElement, UIDivision, UILabel
from core.pygui import PyGui
from core.rendering.interfaces import HasView, View
from core.singletons.asset import AssetLoader

from pygame import Surface, Vector2


def main():
    pyGui = PyGui()
    pyGui.initialize()
    
    pyGui.add_has_view(ExampleHasView(pyGui.asset_loader))
    pyGui.set_active_view('example_view')

    pyGui.run()

    

class ExampleHasView(HasView):

    def __init__(self, asset_loader: AssetLoader) -> None:
        self._asset_loader = asset_loader

    def get_view(self) -> View:
        return ExampleView()

    def get_id(self) -> str:
        return 'example_view'
    
class ExampleView(View):

    def __init__(self):
        self._ui_elements: list[UIElement] = []

    def set_active(self, asset_loader: AssetLoader | None, area: Vector2) -> 'ExampleView':
        # Create 5 labels with sample text
        labels = [
            UILabel(f"Label {i+1}")
            for i in range(5)
        ]
        # Create a division to hold the labels
        self._ui_elements.append(UIDivision(labels))
        return self

    def render(
        self,
        surface: Surface,
        area: Vector2,
        asset_loader: AssetLoader,
        ) -> Surface:
        for element in self._ui_elements:
            element_surface = element.get_surface(asset_loader, area)
            surface.blit(element_surface, (0, 0))
        return surface

    def set_passive(self) -> None:
        pass

    def load_assets_from_file(self, asset_loader: AssetLoader) -> None:
        pass

if __name__ == '__main__':
    main()