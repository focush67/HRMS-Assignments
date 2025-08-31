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

### 📄 License

**MIT**
