import time
import os

from binder.binderd.module import BinderDModule

class LogReader(BinderDModule):
    TAG = "log_reader"

    def _parse_time(self, t):
        return time.strptime(t,  LogSettings.TIME_FORMAT)

    def _get_logs(app, since=None)
        log_file = os.path.join(LogSettings.APPS_DIRECTORY, app + ".log")
        with open(log_file, 'r') as f: 
            # TODO this could be made more efficient
            if since: 
                return [line for line in f.readlines() if self._parse_time(LogSettings.EXTRACT_TIME(line)) > since]
            else:
                return f.readlines()
            
    def _handle_get(msg):
        app = msg.get("app")
        since = msg.get("since")
        if not app:
            return self._error_msg("can only get app logs")
        try:
            if "since" in msg:
                since = self._parse_time(msg.get("since"))
            logs = self._get_logs(app, since)
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
