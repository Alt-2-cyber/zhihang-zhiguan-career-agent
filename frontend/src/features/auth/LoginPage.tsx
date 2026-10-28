import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowRight, BriefcaseBusiness, Check, LockKeyhole } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'

const loginSchema = z.object({
  username: z.string().trim().min(1, '请输入账号'),
  password: z.string().min(1, '请输入密码'),
})

type LoginValues = z.infer<typeof loginSchema>

export function LoginPage({
  onLogin,
}: {
  onLogin: (username: string, password: string) => Promise<void>
}) {
  const [error, setError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({ resolver: zodResolver(loginSchema) })

  const submit = async (values: LoginValues) => {
    setError(null)
    try {
      await onLogin(values.username, values.password)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '登录失败，请稍后重试')
    }
  }

  return (
    <main className="login-page">
      <div className="login-grid-overlay" aria-hidden="true" />
      <header className="login-header">
        <div className="login-brand">
          <span className="login-brand-mark" aria-hidden="true"><BriefcaseBusiness size={19} /></span>
          <div>
            <p className="login-brand-name">职航智管</p>
            <p className="login-brand-subtitle">高校毕业生就业服务系统</p>
          </div>
        </div>
        <span className="login-header-label">CAREER OS · 01</span>
      </header>

      <section className="login-layout">
        <div className="login-intro">
          <span className="login-kicker">CAREER OPERATING SYSTEM</span>
          <h1>让每一次<br /><em>求职行动</em><br />都有下一步。</h1>
          <p>从就业画像到投递复盘，把分散的信息整理成可执行、可验证的职业成长路径。</p>
          <div className="login-feature-list">
            <div><span><Check size={14} /></span><p>AI 结论显示证据来源</p></div>
            <div><span><Check size={14} /></span><p>面试与投递状态持续留存</p></div>
            <div><span><Check size={14} /></span><p>辅导员帮扶形成闭环</p></div>
          </div>
        </div>

        <div className="login-card-wrap">
          <div className="login-card-topline"><span>SECURE ACCESS</span><span>01 / 01</span></div>
          <div className="login-card">
            <div className="login-card-heading">
              <span className="login-lock" aria-hidden="true"><LockKeyhole size={18} /></span>
              <div>
                <h2>进入工作台</h2>
                <p>学生与辅导员使用统一入口</p>
              </div>
            </div>
            <form className="login-form" onSubmit={handleSubmit(submit)} noValidate>
              <label className="login-field">
                <span>账号</span>
                <input {...register('username')} autoComplete="username" placeholder="输入账号" />
                {errors.username ? <small>{errors.username.message}</small> : null}
              </label>
              <label className="login-field">
                <span>密码</span>
                <input {...register('password')} type="password" autoComplete="current-password" placeholder="输入密码" />
                {errors.password ? <small>{errors.password.message}</small> : null}
              </label>

              {error ? <div className="login-error" role="alert">{error}</div> : null}

              <button type="submit" aria-label="登录" disabled={isSubmitting} className="login-submit">
                <span>{isSubmitting ? '正在登录' : '登录工作台'}</span>
                {isSubmitting ? null : <ArrowRight aria-hidden="true" size={17} />}
              </button>
            </form>
            <p className="login-card-footnote">你的数据仅用于就业事务管理与个性化建议。</p>
          </div>
        </div>
      </section>
      <footer className="login-footer"><span>职航智管 / 2026</span><span>AI-assisted · Human-controlled</span></footer>
    </main>
  )
}
