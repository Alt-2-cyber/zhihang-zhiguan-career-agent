import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '../components/AppShell'
import { LoadingState } from '../components/Ui'
import { LoginPage } from '../features/auth/LoginPage'
import { useSession } from './session'

const StudentDashboard = lazy(() => import('../features/student/StudentDashboard').then((module) => ({ default: module.StudentDashboard })))
const ChatPage = lazy(() => import('../features/chat/ChatPage').then((module) => ({ default: module.ChatPage })))
const ProfilePage = lazy(() => import('../features/student/ProfilePage').then((module) => ({ default: module.ProfilePage })))
const PlanPage = lazy(() => import('../features/student/PlanPage').then((module) => ({ default: module.PlanPage })))
const LearningPage = lazy(() => import('../features/student/LearningPage').then((module) => ({ default: module.LearningPage })))
const ExamPage = lazy(() => import('../features/student/ExamPage').then((module) => ({ default: module.ExamPage })))
const TrainingCenterPage = lazy(() => import('../features/student/TrainingCenterPage').then((module) => ({ default: module.TrainingCenterPage })))
const WorkplacePage = lazy(() => import('../features/student/WorkplacePage').then((module) => ({ default: module.WorkplacePage })))
const WorkplaceSessionPage = lazy(() => import('../features/student/WorkplacePage').then((module) => ({ default: module.WorkplaceSessionPage })))
const JobsPage = lazy(() => import('../features/student/JobsPage').then((module) => ({ default: module.JobsPage })))
const JobIntelligencePage = lazy(() => import('../features/student/JobIntelligencePage').then((module) => ({ default: module.JobIntelligencePage })))
const ResumePage = lazy(() => import('../features/student/ResumePage').then((module) => ({ default: module.ResumePage })))
const InterviewPage = lazy(() => import('../features/student/InterviewPage').then((module) => ({ default: module.InterviewPage })))
const InterviewSessionPage = lazy(() => import('../features/student/InterviewPage').then((module) => ({ default: module.InterviewSessionPage })))
const ApplicationBoard = lazy(() => import('../features/student/ApplicationBoard').then((module) => ({ default: module.ApplicationBoard })))
const EmploymentFollowupPage = lazy(() => import('../features/student/EmploymentFollowupPage').then((module) => ({ default: module.EmploymentFollowupPage })))
const ReviewPage = lazy(() => import('../features/student/ReviewPage').then((module) => ({ default: module.ReviewPage })))
const CounselorDashboard = lazy(() => import('../features/counselor/CounselorDashboard').then((module) => ({ default: module.CounselorDashboard })))
const StudentListPage = lazy(() => import('../features/counselor/StudentListPage').then((module) => ({ default: module.StudentListPage })))
const InterventionsPage = lazy(() => import('../features/counselor/InterventionsPage').then((module) => ({ default: module.InterventionsPage })))
const QualityPage = lazy(() => import('../features/counselor/QualityPage').then((module) => ({ default: module.QualityPage })))
const AuditLogsPage = lazy(() => import('../features/counselor/AuditLogsPage').then((module) => ({ default: module.AuditLogsPage })))
const AgentUsagePage = lazy(() => import('../features/counselor/AgentUsagePage').then((module) => ({ default: module.AgentUsagePage })))
const EmployerReviewPage = lazy(() => import('../features/public/EmployerReviewPage').then((module) => ({ default: module.EmployerReviewPage })))

export function AppRouter() {
  const session = useSession()
  if (!session.user) {
    return (
      <Suspense fallback={<LoadingState />}>
        <Routes>
          <Route path="/employer-review/:token" element={<EmployerReviewPage />} />
          <Route path="*" element={<LoginPage onLogin={session.login} />} />
        </Routes>
      </Suspense>
    )
  }

  const home = session.user.role === 'student' ? '/student' : '/counselor'
  const token = session.token!
  const studentOnly = (element: ReactNode) => session.user?.role === 'student' ? element : <Navigate to={home} replace />
  const staffOnly = (element: ReactNode) => session.user?.role !== 'student' ? element : <Navigate to={home} replace />

  return (
    <AppShell>
      <Suspense fallback={<LoadingState />}>
        <Routes>
          <Route path="/student" element={studentOnly(<StudentDashboard token={token} />)} />
          <Route path="/student/assistant" element={studentOnly(<ChatPage token={token} role="student" />)} />
          <Route path="/student/profile" element={studentOnly(<ProfilePage token={token} />)} />
          <Route path="/student/plan" element={studentOnly(<PlanPage token={token} />)} />
          <Route path="/student/learning" element={studentOnly(<LearningPage token={token} />)} />
          <Route path="/student/learning/exams/:examId" element={studentOnly(<ExamPage token={token} />)} />
          <Route path="/student/training" element={studentOnly(<TrainingCenterPage token={token} />)} />
          <Route path="/student/workplace" element={studentOnly(<WorkplacePage token={token} />)} />
          <Route path="/student/workplace/session/:sessionId" element={studentOnly(<WorkplaceSessionPage token={token} />)} />
          <Route path="/student/jobs" element={studentOnly(<JobsPage token={token} />)} />
          <Route path="/student/intelligence" element={studentOnly(<JobIntelligencePage token={token} />)} />
          <Route path="/student/resume" element={studentOnly(<ResumePage token={token} />)} />
          <Route path="/student/interview/:sessionId" element={studentOnly(<InterviewSessionPage token={token} />)} />
          <Route path="/student/interview" element={studentOnly(<InterviewPage token={token} />)} />
          <Route path="/student/applications" element={studentOnly(<ApplicationBoard token={token} />)} />
          <Route path="/student/employment" element={studentOnly(<EmploymentFollowupPage token={token} />)} />
          <Route path="/student/review" element={studentOnly(<ReviewPage token={token} />)} />
          <Route path="/counselor" element={staffOnly(<CounselorDashboard token={token} />)} />
          <Route path="/counselor/assistant" element={staffOnly(<ChatPage token={token} role={session.user.role} />)} />
          <Route path="/counselor/students" element={staffOnly(<StudentListPage token={token} />)} />
          <Route path="/counselor/interventions" element={staffOnly(<InterventionsPage token={token} />)} />
          <Route path="/counselor/quality" element={staffOnly(<QualityPage token={token} />)} />
          <Route path="/counselor/audit" element={staffOnly(<AuditLogsPage token={token} />)} />
          <Route path="/counselor/agent-usage" element={staffOnly(<AgentUsagePage token={token} />)} />
          <Route path="/employer-review/:token" element={<EmployerReviewPage />} />
          <Route path="*" element={<Navigate to={home} replace />} />
        </Routes>
      </Suspense>
    </AppShell>
  )
}
