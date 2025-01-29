import pkgutil
import inspect
import importlib

from pathlib import Path

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def register_all_local_plugins(self):
        from django_resume.plugins import plugin_registry

        plugins_package = f"{self.name}.plugins"

        # Get the path to the plugins directory
        plugins_path = Path(__file__).parent / "plugins"

        all_plugins = []

        # Iterate through all Python modules in the plugins directory
        for _, module_name, _ in pkgutil.iter_modules([plugins_path]):
            full_module_name = f"{plugins_package}.{module_name}"
            try:
                # Dynamically import the plugin module
                module = importlib.import_module(full_module_name)

                # Inspect the module to find all classes
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # Check if the class is defined in the current module
                    if (
                        obj.__module__ == full_module_name
                        and hasattr(obj, "name")
                        and hasattr(obj, "verbose_name")
                    ):
                        all_plugins.append(obj)
                        print(f"Found plugin: {obj.name} ({obj.verbose_name})")
            except Exception as e:
                print(f"Failed to load plugin {module_name}: {e}")

        # Register all discovered plugins
        if len(all_plugins) > 0:
            print("all_plugins: ", all_plugins)
            plugin_registry.register_plugin_list(all_plugins)
            print(f"Registered {len(all_plugins)} plugins.")
        else:
            print("No valid plugins found.")

    # def ready(self) -> None:
    #     self.register_all_local_plugins()
    #     print("core ready!")
