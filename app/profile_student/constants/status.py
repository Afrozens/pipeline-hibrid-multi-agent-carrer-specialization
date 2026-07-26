from enum import Enum


class ProfileStudentStatus(str, Enum):
    PENDING = "pending"
    INCOMPLETE = "incomplete"
    COMPLETE = "complete"
