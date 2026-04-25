Project: Student Portal

Stack:
- NextJS frontend
- Python backend
- PostgreSQL
- Docker deployment

Purpose:
Portal for students/admins to manage enrollment, records, permissions, files, grades.

Critical Areas:
- Authentication
- Role-based access
- Student data protection
- File uploads
- API permissions

Known Risks:
- Auth middleware recently changed
- Unsure if RBAC is airtight
- Unsure about DB indexing
- Unsure about API validation

Review Priority:
1. Security
2. Backend architecture
3. DB integrity
4. Frontend auth
5. Performance