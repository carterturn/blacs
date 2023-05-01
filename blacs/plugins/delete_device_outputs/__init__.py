''' /plugins/delete_device_outputs/__init__.py

 Copyright 2023, cartertu

 This file is part of the program BLACS, in the labscript suite
 (see http://labscriptsuite.org), and is licensed under the
 Simplified BSD License. See the license.txt file in the root of
 the project for the full license.
'''

import logging
import os
import subprocess
import threading
import sys
from queue import Queue

from qtutils import UiLoader

from labscript_utils.shared_drive import path_to_agnostic
from labscript_utils.ls_zprocess import Lock
from blacs.plugins import PLUGINS_DIR

name = "Delete device outputs"
module = "delete_device_outputs" # should be folder name
logger = logging.getLogger('BLACS.plugin.%s'%module)

class Plugin(object):
    def __init__(self, initial_settings):
        self.menu = None
        self.notifications = {}
        self.initial_settings = initial_settings
        self.BLACS = None
        self.ui = None
        self.delete_queue = initial_settings.get('delete_queue', [])
        self.event_queue = Queue()
        self.delete_queue_lock = threading.Lock()
        self.mainloop_thread = threading.Thread(target=self.mainloop)
        self.mainloop_thread.daemon = True
        self.mainloop_thread.start()
        
    def plugin_setup_complete(self, BLACS):
        self.BLACS = BLACS

        # Add controls to the BLACS UI:
        self.ui = UiLoader().load(os.path.join(PLUGINS_DIR, module, 'controls.ui'))
        BLACS['ui'].queue_controls_frame.layout().addWidget(self.ui)

        # Set button to last state
        self.ui.delete_device_outputs_button.setChecked(self.do_delete_device_outputs)

        # Connect signals:
        self.ui.delete_device_outputs_button.clicked.connect(self.on_button_changed)
        BLACS['ui'].queue_repeat_button.toggled.connect(self.ui.setEnabled)

        # Control is only enabled when repeat mode is active:
        self.ui.setEnabled(BLACS['ui'].queue_repeat_button.isChecked())

    def on_button_changed(self, checked):
        with self.delete_queue_lock:
            self.do_delete_device_outputs = checked

    def get_save_data(self):
        return {'do_delete_device_outputs': self.do_delete_device_outputs,
                'delete_queue': self.delete_queue}

    def get_callbacks(self):
        return {'shot_complete': self.on_shot_complete}

    def on_shot_complete(self, h5_filepath):
        # If not deleting device outputs, just return
        if not self.do_delete_device_outputs:
            return

        # Is the file a repeated shot?
        basename, ext = os.path.splitext(os.path.basename(h5_filepath))
        if '_rep' in basename and ext == '.h5':
            repno = basename.split('_rep')[-1]
            try:
                int(repno)
            except ValueError:
                # not a rep:
                return
            else:
                # Yes, it is a rep. Queue it for deletion:
                self.delete_queue.append(h5_filepath)
                self.event_queue.put('shot complete')

    def mainloop(self):
        # We delete outputs in a separate thread so that we don't slow down the queue waiting on
        # network communication to acquire the lock, 
        while True:
            try:
                event = self.event_queue.get()
                if event == 'close':
                    break
                elif event == 'shot complete':
                    while len(self.delete_queue) > self.n_shots_to_keep:
                        with self.delete_queue_lock:
                            h5_filepath = self.delete_queue.pop(0)
                        # Acquire a lock on the file so that we don't
                        # delete it whilst someone else has it open:
                        with Lock(path_to_agnostic(h5_filepath)):
                            with h5py.File(h5_filepath, 'w') as hdf5_file:
                                del hdf5_file['devices']
                                logger.info("Deleted device outputs from %s" % h5_filepath)
)
                else:
                    raise ValueError(event)
            except Exception:
                logger.exception("Exception in device output deletion loop, ignoring.")
    

    def close(self):
        self.event_queue.put('close')
        self.mainloop_thread.join()


    # The rest of these are boilerplate:
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
