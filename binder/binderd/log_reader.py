import datetime
import os

from binder.binderd.module import BinderDModule
from binder.settings import LogSettings
from binder.log import *

class LogReader(BinderDModule):
    TAG = "log_reader"

    def _parse_time(self, t):
        return datetime.datetime.strptime(t,  LogSettings.TIME_FORMAT)

    def _parse_time_line(self, line):
        t = LogSettings.EXTRACT_TIME(line)
        try:
            return self._parse_time(t)
        except Exception as e:
            return datetime.datetime.min

    def _get_logs(self, app, since=None, filtered=False):
        if not filtered:
            log_file = os.path.join(LogSettings.APPS_DIRECTORY, app + ".log")
        else:
            log_file = os.path.join(LogSettings.APPS_DIRECTORY, app + "-filtered.log")
        with open(log_file, 'r') as f: 
            # TODO this could be made more efficient
            if since: 
                # buffer the whole file (will have to anyway for now) 
                def _line_filter(line):
                    return line != '' and self._parse_time_line(line) > since
                return "\n".join(map(lambda l: l.strip(), filter(_line_filter, f.readlines())))
            else:
                return f.read()
            
    def _handle_get(self, msg):
        app = msg.get("app")
        since = msg.get("since")
        filtered = msg.get("filtered")
        if filtered:
            filtered = bool(filtered)
        if not app:
            return self._error_msg("can only get app logs")
        try:
            if since:
                since = self._parse_time(msg.get("since"))
            logs = self._get_logs(app, since, filtered)
            return self._success_msg(logs)
        except Exception as e:
            return self._error_msg("couldn't get app logs: {}".format(e))

    def _handle_message(self, msg):
        """
        BinderDModule interface
        """
        msg_type = msg.get("type")
        if msg_type == 'get':
            return self._handle_get(msg)
