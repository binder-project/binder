
from subprocess import Popen

from binder.binderd.module import BinderDModule
from binder.settings import MainSettings

class KubeProxy(BinderDModule):
    TAG = "kube_proxy"

    def __init__(self):
        super(KubeProxy, self).__init__()
        # set in _initialize
        self._proxy_proc = None

    def _initialize(self):
        super(KubeProxy, self)._initialize()
        # start the proxy process
        self._proxy_proc = Popen(['kubectl.sh', 'proxy', '--port={}'.format(MainSettings.KUBE_PROXY_PORT)])

    def _handle_stop(self):
        super(KubeProxy, self)._handle_stop()
        # stop the proxy process
        if self._proxy_proc:
            self._proxy_proc.kill()
            self._proxy_proc.wait()
        

