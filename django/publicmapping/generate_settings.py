#!/usr/bin/python
from optparse import OptionParser
import sys
from redistricting import StoredConfig
import logging

logging.basicConfig(format='%(message)s')
logging._srcFile = None
logging.logThreads = 0
logging.logProcesses = 0

logger = logging.getLogger()

def main():
    """
    Main method to start the setup of DistrictBuilder.
    """
    usage = "usage: %prog [options] SCHEMA CONFIG"
    parser = OptionParser(usage=usage)
    parser.add_option('-v', '--verbosity', dest="verbosity",
            help="Verbosity level; 0=minimal output, 1=normal output, 2=all output",
            default=1, type="int")

    (options, args) = parser.parse_args()

    setup_logging(options.verbosity)

    if len(args) != 2:
        logger.warning("""
ERROR:

    This script requires a configuration file and a schema. Please check
    the command line arguments and try again.
""")
        sys.exit(1)

    try:
        config = StoredConfig(args[1], schema_file=args[0])
    except Exception as e:
        logger.exception("Error initializing config")
        sys.exit(1)

    if not config.validate():
        logger.info("Configuration could not be validated.")
        sys.exit(1)

    logger.info("Validated config.")

    status = config.write_settings()
    if status:
        logger.info("Generated Django settings.")
    else:
        logger.info("Failed to generate settings.")
        sys.exit(1)

    # Success! Exit-code 0
    sys.exit(0)

def setup_logging(verbosity):
    """
    Setup logging for setup.
    """
    if verbosity > 1:
        logger.setLevel(logging.DEBUG)
    elif verbosity > 0:
        logger.setLevel(logging.INFO)

if __name__ == "__main__":
    main()
