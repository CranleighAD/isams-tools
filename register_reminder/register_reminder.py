import datetime as dt
import logging
import sys

from settings import *
from utils import isams_connection
from utils.isams_email import ISAMSEmail

# make sure this isn't called directly
if __name__ == "__main__":
    sys.stderr.write('Please use bin/isams_tools instead\n')
    sys.exit(1)

logger = logging.getLogger('root')


def send_tutor_emails(unregistered_students, stage):
    """Prepares the email list and email templates in order to send them

    :param teachers: the list of teacher dicts to send the email to, containing email, forename, surname, form
    :param stage: which stage email to send
    :return: None
    """
    bcc = ""
    list_of_missing_registers = ""
    message = ""
    tutor_list = {}


    # create a unique list of tutors with unregistered students
    for student in unregistered_students:
        if student.form.teacher.id not in tutor_list:
            # looks a bit silly but we need it later on
            student.form.teacher.form = student.form
            tutor_list[student.form.teacher.id] = student.form.teacher

    # compile the BCC list as well as the text for %list_of_missing_registers%
    i = 0
    for tutor_id in tutor_list:
        tutor = tutor_list[tutor_id]
        if tutor.email:
            bcc += tutor.email

        # don't put a comma for the last entry
        if i < len(tutor_list) - 1:
            bcc += ", "

        list_of_missing_registers += "{0}: {1} {2}\n".format(tutor.form.name,  tutor.forename,  tutor.surname)

        i += 1

    to = EMAIL['to']

    # TODO: this could be customisable
    if str(stage) == "1":
        message = FIRST_EMAIL
    elif str(stage) == "2":
        message = SECOND_EMAIL
    elif str(stage) == "3":
        message = FINAL_EMAIL
        to = FINAL_EMAIL_TO

    # if the template uses the variable, replace is with the list of teachers
    message = message.replace('%list_of_missing_registers%', list_of_missing_registers)

    if DEBUG:
        message += "\n\nThis a debug email, the intented recipients were: " + bcc
        message += "\n\nStage " + str(stage)
        logger.debug("BCC list before we bin it: " + bcc)

        # if we're debugging, get rid of the BCC list, i.e. the intended teachers
        bcc = ""

    # create the email but don't send yet
    email = ISAMSEmail(EMAIL['subject'], message, to, EMAIL['from'], bcc)

    if SEND_EMAILS:
        email.send()
    else:
        logger.debug("Email not sent as we're in debug mode")


class RegisterReminder:
    """A class to setup and execute a register reminder"""
    start_date = None
    end_date = None
    connection = None
    tree = None

    def __init__(self, start_date, end_date, stage):
        logger.debug("RegisterReminder({0}. {1}, {2}".format(start_date, end_date, stage))
        """RegisterReminder constructor

        :param start_date: the start of the registration period, i.e. today, in the format YYYY-MM-DD
        :param end_date: the end of the registration period, i.e. tomorrow, in the format YYYY-MM-DD
        :param stage: which stage of the reminders to run (1-3) which determines which email template to use
        """
        self.start_date = start_date
        self.end_date = end_date

        # create the connection to ISAMS
        self.connection = isams_connection.ISAMSConnection(URL, start_date, end_date)

        # compile a unique list of tutors with unregistered kids
        unregistered_students = self.get_unregistered_students()

        # no point sending a blank emails
        if unregistered_students:
            # send those tutors an email to remind them
            send_tutor_emails(unregistered_students, stage)
        else:
            logger.info("No unregistered students, exiting")
            exit(0)

    def get_unregistered_students(self):
        unregistered_students = []
        tree = self.connection.get_tree()
        for register_entry in tree.iter('RegistrationStatus'):
            registration_status = int(register_entry.find('Registered').text)
            present_code = None

            try:
                present_code = int(register_entry.find('Code').text)
            except AttributeError:
                pass

            if registration_status == 0 and not present_code:
                isams_id = register_entry.find('PupilId').text
                student = self.connection.get_student(isams_id, False)

                # if we have a student who leaves this can sometimes be None
                if student:
                    unregistered_students.append(student)

        if DEBUG:
            # self.unregistered_students.append(self.get_student('091159705547', False))
            pass

        return unregistered_students


def run(stage=1):
    """Creates and runs a RegisterReminder() instance after making a few sanity checks

    :param stage: the stage of reminder to run, 1 to 3 (default 1)
    :return: None
    """
    # do some basic checks to see if we should be running
    logger.debug("run({0})")
    if ENABLED:
        today_dt = dt.datetime.today()
        tomorrow = (today_dt + dt.timedelta(days=1)).strftime('%Y-%m-%d')
        today = today_dt.strftime('%Y-%m-%d')

        if DEBUG:
            if DEBUG_START_DATE and DEBUG_END_DATE:
                RegisterReminder(DEBUG_START_DATE, DEBUG_END_DATE, stage)
            else:
                RegisterReminder(today, tomorrow, stage)
        else:
            if today in HOLIDAYS:
                logger.info("Today is a holiday, exiting")
                sys.exit(0)

            if today_dt.weekday() not in WORKING_DAYS:
                logger.warning("Today is a weekend, you need to fix your cronjob")
                sys.exit(1)

            RegisterReminder(today, tomorrow, stage)
    else:
        logger.critical("Not running: disabled in settings")
