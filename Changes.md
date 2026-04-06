# Database Change Log

## Change #1 — 2026-04-06 16:36:43
- **Type:** UPDATE
- **Table:** employees
- **Rows Affected:** 1
- **SQL:** `UPDATE employees SET gender = 'Male', email = 'jdobbin@workspace.edu' WHERE id = 1 RETURNING id, first_name, last_name, email, gender;`

---

