# coding=utf-8
from __future__ import absolute_import

import time
import traceback

import octoprint.plugin as plugin
import octoprint.util as util
from octoprint.events import Events


class CuraM73Plugin(plugin.EventHandlerPlugin,
                    plugin.SettingsPlugin,
                    plugin.TemplatePlugin):
    def __init__(self):
        self._command_format = ['M73 P{0} R{1} Q{0} S{1}']
        self._data_update_time = 0.0
        self._data = None
        self._progress = 0
        self._time_left = 0
        self._repeat_timer = None

        super(CuraM73Plugin, self).__init__()

    @property
    def commands(self):
        return [cmd.format(self.progress, self.time_left) for cmd in self._command_format]

    @property
    def data(self):
        if time.time() - self._data_update_time >= 1.0:
            self._data = self._printer.get_current_data()
            self._data_update_time = time.time()
        return self._data

    @property
    def progress(self):
        try:
            self._progress = int(round(self.data['progress']['completion']))
        except TypeError:
            self._progress = 0
        return self._progress

    @property
    def time_left(self):
        time_left = self.data['progress']['printTimeLeft']

        if time_left == None:
            time_left = self.data['job']['estimatedPrintTime']

        try:
            self._time_left = int(round(time_left / 60))
        except TypeError:
            self._time_left = 0
        return self._time_left

    @handle_gracefully
    def on_event(self, event, payload):
        if event == Events.PRINT_STARTED:
            file_name = self._printer.get_current_data()['job']['file']['name']
            if file_name.lower().startswith(self._settings.get(['cura_prefix']).lower()):
                self._repeat_timer = util.RepeatedTimer(self._settings.get_int(['update_interval']), self.do_work)
                self._repeat_timer.start()
                self.log('{} is a Cura file, enabling M73'.format(file_name))
            else:
                self.log('{} is not a Cura file, disabling M73'.format(file_name))

        elif event in (Events.PRINT_DONE, Events.PRINT_FAILED, Events.PRINT_CANCELLED):
            if self._repeat_timer != None:
                self._repeat_timer.cancel()
                self._repeat_timer = None
                self.log('Print finished, stopping M73')
            else:
                self.log('Print finished, M73 already disabled')

    @handle_gracefully
    def do_work(self):
        if self._printer.is_printing():
            self._printer.commands(self.commands)
            self.log('Updating progress: P{} R{}'.format(self.progress, self.time_left))

    def log(self, msg):
        self._logger.info(msg)

    def get_settings_defaults(self):
        return dict(
            update_interval = 15,
            cura_prefix = 'OPI3MK3'
        )

    def get_update_information(self):
        return dict(
            curam73 = dict(
                displayName = self._plugin_name,
                displayVersion = self._plugin_version,

                type = 'github_release',
                user = 'Spectrewiz',
                repo = 'OctoPrint-CuraM73',
                current = self._plugin_version,

                pip = 'https://github.com/Spectrewiz/OctoPrint-CuraM73/archive/{target_version}.zip'
            )
        )

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False)
        ]


def handle_gracefully(func):
    def graceful(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            global __plugin_implementation__
            __plugin_implementation__.log('Caught an exception {0}\nTraceback:\n{1}'.format(e, traceback.format_exc()))
    return graceful


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = CuraM73Plugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        'octoprint.plugin.softwareupdate.check_config': __plugin_implementation__.get_update_information
    }
