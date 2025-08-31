## HRMS Assignments Submission

This application is a submission to the HRMS assignment given from GirmanTech

#### License

mit

Assignment 1: HRMS and Recruitment

    Following were the objectives for this assignment:
    1. Create a custom Recruitment Workflow
        . Job Opening -> Application -> Screening -> Interview -> Offer -> Hired
        . Configure appropriate role-based permissions.
        . Add a custom field in "Job Applicant" for "Source of Application".
        . Build a report/dashboard showing the number of applicants per source.

Challenges and Solutions:

    1. In the interview.py file, the whitelisted function update_job_applicant_status(job_applicant:str,status:str) is being triggered with a server action inside the function show_job_applicant_update_dialog(self) inside of core hrms module backend. However there seems to be an internal code issue due to which when the arguments get passed to this function through this server action, they become None. Hence the function update_job_applicant_status() throws an error for missing arguments. To circumvent this, I have removed the dialog box for server action and instead, added the validation that "Accepted" in Job Applicant can only be set when all the Interviews are marked as Cleared. So when the last interview is cleared, only then will the status change to Accepted.
