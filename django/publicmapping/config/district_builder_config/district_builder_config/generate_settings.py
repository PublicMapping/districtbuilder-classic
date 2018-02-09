#!/usr/bin/python
import argparse
import sys
from . import StoredConfig
import logging

logging.basicConfig(format='%(message)s')
logging._srcFile = None
logging.logThreads = 0
logging.logProcesses = 0

logger = logging.getLogger()

def main():
    parser = argparse.ArgumentParser(
        description='Generate settings file based on configuration')
    parser.add_argument('schema', help='path to schema file used for validation')
    parser.add_argument('config', help='path to config file')
    parser.add_argument('output_path', help='path that generated settings file will be written to')
    parser.add_argument('-v', '--verbosity', dest="verbosity",
            help="Verbosity level; 0=minimal output, 1=normal output, 2=all output",
            default=1, type=int)

    args = parser.parse_args()

    setup_logging(args.verbosity)

    if len(sys.argv) != 4:
        logger.warning("""
ERROR:

    This script requires a schema, a configuration file, and an output path for
    the settings file that is generated. Please check the command line
    arguments and try again.
""")
        sys.exit(1)

    try:
        config = StoredConfig(args.config, schema_file=args.schema)
    except Exception as e:
        logger.exception("Error initializing config")
        sys.exit(1)

    if not config.validate():
        logger.info("Configuration could not be validated.")
        sys.exit(1)

    logger.info("Validated config.")

    status = config.write_settings(output_path=args.output_path)
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
