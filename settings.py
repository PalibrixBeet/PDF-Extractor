import json
import os
import pathlib


class Settings:
    """
    Handle loading, saving, and managing application settings.
    """

    def __init__(self):
        self.settings_file = os.path.join(pathlib.Path(__file__).parent.absolute(), 'pdf_reader_settings.json')
        self.settings = self._get_default_settings()
        self.load_settings()

    def _get_default_settings(self):
        return {
            'last_directory': str(pathlib.Path(__file__).parent.absolute()),
            'reader_type': 'plumber',  # or 'pymupdf'
            'start_page': 1,
            'end_page': 0,
            'extract_filetype': 'jsonl',
            '_mode': 'r',  # or 'c'
            'dehyphenate': True,
            'html_like': False,
            'y_tolerance': 3,
            'x_tolerance': 1.5,
            'borders': [None, None, None, None],  # [header, left, right, footer]
        }

    def load_settings(self):
        """
        Load settings from file if exists, otherwise use defaults.
        """
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    loaded_settings = json.load(f)

                # Update default settings with loaded values
                for key, value in loaded_settings.items():
                    self.settings[key] = value

                return True
        except Exception as e:
            print(f"Error loading settings: {e}")

        return False

    def save_settings(self):
        """
        Save current settings to file.
        """
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def get_setting(self, key, default=None):
        """
        Get a specific setting by key.

        Args:
            key (str): Setting key
            default: Default value if key not found

        Returns:
            Value of the setting or default if not found
        """
        return self.settings.get(key, default)

    def update_setting(self, key, value):
        """
        Update a specific setting.

        Args:
            key (str): Setting key
            value: New value for the setting
        """
        self.settings[key] = value

    def get_all_settings(self):
        """
        Get all settings.

        Returns:
            dict: All settings
        """
        return self.settings.copy()