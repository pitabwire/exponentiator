import logging
import os
import time

from application import Exponentiator
from utility import get_service_name

log = logging.getLogger(__name__)

ENVIRONMENT_SLEEP_DURATION_KEY = 'SLEEP_DURATION'


class DaemonApp:

    def __init__(self):
        self.exponentiator = None

    def setup(self, application_name):

        self.exponentiator = Exponentiator()
        log.debug(" setup -- Setting up application configuration for [%s]", application_name)

    def run(self, application_name):
        should_run = True
        error_retry_duration = 1
        log.info(" run -- Initiating application  [%s]", application_name)

        while should_run:

            try:
                self.exponentiator.execute_check(compound_pct=100)

                sleep_duration = os.getenv(ENVIRONMENT_SLEEP_DURATION_KEY, 5 * 60)
                log.debug(" run -- sleeping for %s before checking again, Edit Env [%s]", sleep_duration,
                          ENVIRONMENT_SLEEP_DURATION_KEY)
                time.sleep(sleep_duration)
                error_retry_duration = 1

            except KeyboardInterrupt:
                exit(0)
            except Exception as e:
                log.error(" run -- seems there is an issue executing check ", exc_info=True)

                # when there are errors in the network we wait for a shorter period before retrying
                # Using an exponential retry mechanism until we are waiting for 10 minutes

                if error_retry_duration < 600:
                    error_retry_duration *= 2

                time.sleep(error_retry_duration)

    @classmethod
    def clean_up(cls):
        pass

    @classmethod
    def reload_configs(cls):
        pass


if __name__ == '__main__':
    daemon_app = DaemonApp()
    daemon_app.setup(application_name=get_service_name())
    daemon_app.run(application_name=get_service_name())
