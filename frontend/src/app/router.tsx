import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '../components/AppShell'
import { LoadingState } from '../components/Ui'
import { LoginPage } from '../features/auth/LoginPage'
import { useSession } from './session'

const StudentDashboard = lazy(() => import('../features/student/StudentDashboard').then((module) => ({ default: module.StudentDashboard })))
const ProfilePage = lazy(() => import('../features/student/ProfilePage').then((module) => ({ default: module.ProfilePage })))
const PlanPage = lazy(() => import('../features/student/PlanPage').then((module) => ({ default: module.PlanPage })))
const JobsPage = lazy(() => import('../features/student/JobsPage').then((module) => ({ default: module.JobsPage })))
const ResumePage = lazy(() => import('../features/student/ResumePage').then((module) => ({ default: module.ResumePage })))
const InterviewPage = lazy(() => import('../features/student/InterviewPage').then((module) => ({ default: module.InterviewPage })))
const ApplicationBoard = lazy(() => import('../features/student/ApplicationBoard').then((module) => ({ default: module.ApplicationBoard })))
const ReviewPage = lazy(() => import('../features/student/ReviewPage').then((module) => ({ default: module.ReviewPage })))
const CounselorDashboard = lazy(() => import('../features/counselor/CounselorDashboard').then((module) => ({ default: module.CounselorDashboard })))
const StudentListPage = lazy(() => import('../features/counselor/StudentListPage').then((module) => ({ default: module.StudentListPage })))
const InterventionsPage = lazy(() => import('../features/counselor/InterventionsPage').then((module) => ({ default: module.InterventionsPage })))

export function AppRouter() {
  const session = useSession()
  if (!session.user) return <LoginPage onLogin={session.login} />

  const home = session.user.role === 'student' ? '/student' : '/counselor'
  const token = session.token!
  return (
    <AppShell>
      <Suspense fallback={<LoadingState />}>
        <Routes>
          <Route path="/student" element={session.user.role === 'student' ? <StudentDashboard token={token} /> : <Navigate to={home} replace />} />
          <Route path="/student/profile" element={session.user.role === 'student' ? <ProfilePage token={token} /> : <Navigate to={home} replace />} />
          <Route path="/student/plan" element={session.user.role === 'student' ? <PlanPage token={token} /> : <Navigate to={home} replace />} />
          <Route path="/student/jobs" element={session.user.role === 'student' ? <JobsPage token={token} /> : <Navigate to={home} replace />} />
          <Route path="/student/resume" element={session.user.role === 'student' ? <ResumePage token={token} /> : <Navigate to={home} replace />} />
          <Route path="/student/interview" element={session.user.role === 'student' ? <InterviewPage token={token} /> : <Navigate to={home} replace />} />
          <Route path="/student/applications" element={session.user.role === 'student' ? <ApplicationBoard token={token} /> : <Navigate to={home} replace />} />
          <Route path="/student/review" element={session.user.role === 'student' ? <ReviewPage token={token} /> : <Navigate to={home} replace />} />
          <Route path="/counselor" element={session.user.role !== 'student' ? <CounselorDashboard token={token} /> : <Navigate to={home} replace />} />
          <Route path="/counselor/students" element={session.user.role !== 'student' ? <StudentListPage token={token} /> : <Navigate to={home} replace />} />
          <Route path="/counselor/interventions" element={session.user.role !== 'student' ? <InterventionsPage token={token} /> : <Navigate to={home} replace />} />
          <Route path="*" element={<Navigate to={home} replace />} />
        </Routes>
      </Suspense>
    </AppShell>
  )
}
