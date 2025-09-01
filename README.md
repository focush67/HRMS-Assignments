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

### 📄 License

**MIT**
