
# Lists the available binderd modules and the type of client socket necessary to communicate with them

from binder.binderd.log_writer import LogWriter
from binder.binderd.log_reader import LogReader
import zmq

modules = { 
    'log_reader': LogReader, 
    'log_writer': LogWriter
}

