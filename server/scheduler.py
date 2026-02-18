"""class to manage schedules"""

import datetime

from logger import mylog
from utils.datetime_utils import timeNowTZ


# -------------------------------------------------------------------------------
class schedule_class:
    def __init__(
        self,
        service,
        scheduleObject,
        last_next_schedule,
        was_last_schedule_used,
        last_run=0,
    ):
        self.service = service
        self.scheduleObject = scheduleObject
        self.last_next_schedule = last_next_schedule
        self.last_run = last_run
        self.was_last_schedule_used = was_last_schedule_used

    def runScheduleCheck(self):
        result = False

        # Initialize the last run time if never run before
        if self.last_run == 0:
            self.last_run = (
                timeNowTZ(as_string=False) - datetime.timedelta(days=365)
            ).replace(microsecond=0)

        # get the current time with the currently specified timezone
        nowTime = timeNowTZ(as_string=False)

        # Run the schedule if the current time is past the schedule time we saved last time and
        #               (maybe the following check is unnecessary)
        if nowTime > self.last_next_schedule:
            mylog("verbose", f"[Scheduler] run for {self.service}: YES")
            self.was_last_schedule_used = True
            result = True
        else:
            mylog("verbose", f"[Scheduler] run for {self.service}: NO")
            # mylog('debug',f'[Scheduler] - nowTime {nowTime}')
            # mylog('debug',f'[Scheduler] - self.last_next_schedule {self.last_next_schedule}')
            # mylog('debug',f'[Scheduler] - self.last_run {self.last_run}')

        if self.was_last_schedule_used:
            self.was_last_schedule_used = False
            self.last_next_schedule = self.scheduleObject.next()

        return result
