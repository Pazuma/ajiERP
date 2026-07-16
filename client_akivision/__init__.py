__version__ = "0.0.1"

from client_akivision import utils
from client_akivision.utils.safety_stock_reorder import patch_reorder_module

patch_reorder_module()
