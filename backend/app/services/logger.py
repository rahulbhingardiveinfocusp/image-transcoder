import logging
import sys
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [BRIDGE-SCRIPT] %(message)s"
)
logger = logging.getLogger(__name__)