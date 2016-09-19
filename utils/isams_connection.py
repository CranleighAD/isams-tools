import logging
from xml.etree import ElementTree
from settings import DEBUG

import requests
import sys

logger = logging.getLogger('root')


class ISAMSConnection:
    tree = None
    all_students = {}
    unregistered_students = []
    filters = None
    start_date = None
    end_date = None

    def __init__(self, url, start_date, end_date):
        self.start_date = start_date
        self.end_date = end_date

        # as we need to get all data, even if we're not looking at register we still need the filters
        self.filters = """<?xml version='1.0' encoding='utf-8'?>
        <Filters>
            <RegistrationManager>
                <RegistrationStatus startDate="{0}" endDate="{1}" />
            </RegistrationManager>
        </Filters>
        """.format(self.start_date, self.end_date)

        logger.debug("Filters:" + self.filters)
        headers = {'Content-Type': 'application/xml'}
        r = requests.post(url, data=self.filters, headers=headers)
        logger.debug("Opening connection to: " + url)
        xml = r.text
        xml = xml.encode('utf16')
        tree = ElementTree.fromstring(xml)

        self.tree = tree
        self.all_students = self.get_all_students()

    def get_tree(self) -> ElementTree:
        return self.tree

    def get_all_students(self):
        if not self.tree:
            logger.critical("Can't get students as no active iSAMS connection")
            sys.exit(1)

        for this_student in self.tree.iter('Pupil'):
            isams_id = this_student.find('SchoolId').text
            forename = this_student.find('Forename').text
            surname = this_student.find('Surname').text
            # username = this_student.find('UserName').text
            username = None
            # email = this_student.find('EmailAddress').text
            email = None
            form = this_student.find('Form').text
            academic_year = this_student.find('NCYear').text
            form = self.get_form_from_name(this_student.find('Form').text)

            student = ISAMSStudent(isams_id, forename, surname, username, email, academic_year, form)
            self.all_students[isams_id] = student
            if isams_id not in self.all_students.keys():
                print("Didn't manage to add " + isams_id)
            if isams_id == '043858705547':
                print(student)
                print(self.all_students[isams_id])
        return self.all_students

    def get_student(self, isams_id):
        if isams_id in self.all_students:
            student =  self.all_students[isams_id]
        else:
            student = None
        return student

    def get_unregistered_students(self):
        for register_entry in self.tree.iter('RegistrationStatus'):
            registration_status = int(register_entry.find('Registered').text)
            if registration_status == 0:
                isams_id = register_entry.find('PupilId').text
                student = self.get_student(isams_id)

                # if we have a student who leaves this can sometimes be None
                if student:
                    self.unregistered_students.append(student)

        if DEBUG:
            self.unregistered_students.append(self.get_student('091159705547'))

        return self.unregistered_students

    def get_form_from_name(self, form_name):
        form_data = self.tree.findall('.//Form/[@Id="' + form_name + '"]')[0]
        tutor_id = form_data.get('TutorId')
        academic_year = form_data.find('NationalCurriculumYear').text
        logging.debug("Looking for tutor with ID {0}".format(tutor_id))

        try:
            tutor_data = self.tree.findall('.//StaffMember/[@Id="' + tutor_id + '"]')[0]
            forename = tutor_data.find('Forename').text
            surname = tutor_data.find('Surname').text
            username = tutor_data.find('UserName').text
            email = tutor_data.find('SchoolEmailAddress').text
        except IndexError as e:
            # we have a invalid (e.g. left) tutor which can happen, we have to ignore this
            logging.warning(
                "Error when finding the tutor of form {0}, this needs to be fixed in iSAMS".format(form_data))
            logging.warning(str(e))

        tutor = ISAMSTeacher(forename, surname, username, email)
        form = ISAMSForm(form_name, tutor, academic_year)

        return form


class ISAMSTeacher():
    forename = ""
    surname = ""
    username = ""
    email = ""

    def __init__(self, forename, surname, username, email):
        self.forename = forename
        self.surname = surname
        self.username = username
        self.email = email


    def __str__(self):
        return ("({0}, {1}, {2})".format(self.forename, self.surname, self.email))


class ISAMSStudent():
    isams_id = None
    forename = ""
    surname = ""
    username = ""
    email = ""
    academic_year = None
    form = None

    def __init__(self, isams_id, forename, surname, username, email, academic_year, form):
        self.isams_id = isams_id
        self.forename = forename
        self.surname = surname
        self.username = username
        self.email = email
        self.academic_year = academic_year
        self.form = form

    def __str__(self):
        return "({0}, {1}, {2}, {3}, {4}, {5})".\
            format(self.isams_id, self.forename, self.surname, self.username, self.email, self.academic_year)

class ISAMSForm():
    name = ""
    teacher = None
    academic_year = None

    def __init__(self, name, teacher, academic_year):
        self.name = name
        self.teacher = teacher
        self.academic_year = academic_year

    def __str__(self):
        return ("({0}, {1}, {2})".format(self.name, self.teacher, self.academic_year))
