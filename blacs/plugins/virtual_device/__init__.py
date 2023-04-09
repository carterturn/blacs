#####################################################################
#                                                                   #
# /plugins/virtual_device/__init__.py                               #
#                                                                   #
# Copyright 2023, Carter Turnbaugh                                  #
#                                                                   #
#####################################################################
import logging
import os
import subprocess
import threading
import sys
import time

from qtutils import inmain, inmain_decorator

import labscript_utils.h5_lock
import h5py

import labscript_utils.properties as properties
from labscript_utils.connections import ConnectionTable
from zprocess import TimeoutError
from labscript_utils.ls_zprocess import Event
from blacs.plugins import PLUGINS_DIR, callback
from user_devices.virtual_device.blacs_tabs import VirtualDeviceTab

name = "Virtual Device"
module = "virtual_device" # should be folder name
logger = logging.getLogger('BLACS.plugin.%s'%module)

# Try to reconnect often in case a tab restarts
CONNECT_CHECK_INTERVAL = 0.1

class Plugin(object):
    def __init__(self, initial_settings):
        self.menu = None
        self.notifications = {}
        self.initial_settings = initial_settings
        self.BLACS = None
        self.disconnected_last = False
        self.reconnect_thread = threading.Thread(target=self.reconnect)
        self.reconnect_thread.daemon = True

        self.tab_restart_receiver = lambda dn, s=self: self.disconnect_widgets(dn)
        
    def on_tab_layout_change(self):
        self.connect_widgets()

    def plugin_setup_complete(self, BLACS):
        self.BLACS = BLACS

        self.virtual_devices = {}

        for device_name, device_tab in self.BLACS['ui'].blacs.tablist.items():
            if isinstance(device_tab, VirtualDeviceTab):
                self.virtual_devices[device_name] = device_tab

        self.reconnect_thread.start()

    @inmain_decorator(True)
    def connect_widgets(self):
        for name, vd in self.virtual_devices.items():
            # Prevents error when underlying AO/DO is deleted during tab restart
            vd.connect_restart_receiver(self.tab_restart_receiver)

            for full_conn_name, do_widget in vd.do_widgets.items():
                if do_widget.closing:
                    # If widget is in a tab being closed, skip
                    continue
                if do_widget.get_DO():
                    # If widget is already connected, skip
                    continue

                device_name = full_conn_name.split('.').pop(0)
                connection_name = full_conn_name.split('.').pop(1)

                device_tab = self.BLACS['ui'].blacs.tablist[device_name]

                if do_widget.last_DO == device_tab._DO[connection_name]:
                    # Restart was too soon, try again later
                    continue

                # Sync widget with underlying DO
                do_widget.state = device_tab._DO[connection_name].value
                # Assign DO to widget
                do_widget.set_DO(device_tab._DO[connection_name])

                # Prevents error when underlying DO is deleted during tab restart
                device_tab.connect_restart_receiver(self.tab_restart_receiver)

            for full_conn_name, ao_widget in vd.ao_widgets.items():
                if ao_widget.closing:
                    # If widget is in a tab being closed, skip
                    continue
                if ao_widget.get_AO():
                    # If widget is already connected, skip
                    continue

                device_name = full_conn_name.split('.').pop(0)
                connection_name = full_conn_name.split('.').pop(1)

                device_tab = self.BLACS['ui'].blacs.tablist[device_name]

                if ao_widget.last_AO == device_tab._AO[connection_name]:
                    # Restart was too soon, try again later
                    continue

                # Sync widget with underlying AO
                ao_widget.state = device_tab._AO[connection_name].value
                # Assign AO to widget
                ao_widget.set_AO(device_tab._AO[connection_name])

                # Prevents error when underlying AO is deleted during tab restart
                device_tab.connect_restart_receiver(self.tab_restart_receiver)

    @inmain_decorator(True)
    def disconnect_widgets(self, device_name):
        if device_name in self.virtual_devices.keys():
            for _, do_widget in self.virtual_devices[device_name].do_widgets.items():
                do_widget.set_DO(None)
                do_widget.closing = True
            for _, ao_widget in self.virtual_devices[device_name].ao_widgets.items():
                ao_widget.set_AO(None)
                ao_widget.closing = True
            return

        for name, vd in self.virtual_devices.items():
            for full_conn_name, do_widget in vd.do_widgets.items():
                if full_conn_name.split('.').pop(0) == device_name:
                    do_widget.last_DO = do_widget.get_DO()
                    do_widget.set_DO(None)

            for full_conn_name, ao_widget in vd.ao_widgets.items():
                if full_conn_name.split('.').pop(0) == device_name:
                    ao_widget.last_AO = ao_widget.get_AO()
                    ao_widget.set_AO(None)

    def reconnect(self):
        while True:
            self.connect_widgets()
            time.sleep(CONNECT_CHECK_INTERVAL)

    # Standard plugin boilerplate
    def get_save_data(self):
        return {}
    
    def get_callbacks(self):
        return {}

    def get_menu_class(self):
        return None
        
    def get_notification_classes(self):
        return []
        
    def get_setting_classes(self):
        return []
    
    def set_menu_instance(self, menu):
        self.menu = menu
        
    def set_notification_instances(self, notifications):
        self.notifications = notifications
        
    def close(self):
        pass
