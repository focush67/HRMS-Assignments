# 💼 HRMS Assignments Submission

_Submission for the HRMS assignment by **GirmanTech**._

---

## Assignment 1: HRMS and Recruitment

### **Objectives**

- **Custom Recruitment Workflow:**
  - **Flow:** `Job Opening → Application → Screening → Interview → Offer → Hired`
  - **Permissions:** Configured _role-based permissions_ for each stage
  - **Custom Field:** Added `"Source of Application"` to the Job Applicant form
  - **Analytics:** Dashboard/report for applicant count per source

---

### **Challenges & Solutions**

**Issue**  
In `interview.py`, the whitelisted function  
`update_job_applicant_status(job_applicant: str, status: str)`  
is triggered by a server action in  
`show_job_applicant_update_dialog(self)` (_core HRMS backend_).  
Arguments are passed as **None**, causing errors.

**Solution**

- Removed the dialog box for the server action
- Added validation:
  - “Accepted” status for **Job Applicant** is only set when all interviews are marked as **Cleared**
  - Status changes to **Accepted** when the last interview is cleared

---

## Assignment 2: Employee Lifecycle

### **Objectives**

- **Configuring Employee doctype to handle lifecycle events**

  - **Flow:** `Joining -> Probation -> Confirmation -> Exit`
  - **Automation:** Confirmation leads to auto-updation of employee status. Exiting leads to auto generation of Experience Letter PDF, which attaches to the employee itself.

- **Implemented following features**

  - **Probation Evaluation** Created a new doctype called Probation Evaluation, which will serve as the point from where the employee master is updated based on the status.If the total average score around the parameters >= 70%, only then is the employee considered 'Confirmed'.

  - **Updating Employee based on Probation** When the Probation is submitted, based on the status, the new custom field inside of Employee (Is Under Probation) in unchecked, marking the current employee as a normal full-time employee. Also when a new employee is created, they are by default under probation with a time period of 60 days, which can be changed if need be.

  - **Triggering Separation Upon Failed Probation** When the probation fails, the Employee Separation is auto-triggered and upon its completion, employee is marked as Left in the master (this part is done through a background job; hooks could not track the change the Employee Separation document from Pending to Completed, possibly due to the core HRMS using direct DB manipulation and preventing hooks triggering)

  - **Giving Provision of Employee Resignation** Employees can fill their resignation forms for initiating their exit voluntarily. This goes through the same process as above, except now the initiation happens when the Employee Resignation is Submitted.

  - **Experience Letter Generation Upon Exit** When the employee is marked as Left, the Experience Letter is generated and auto-attached to the said employee, stating the essential information like tenure, department and other employee related detail in a professional format.

### 📄 License

**MIT**
