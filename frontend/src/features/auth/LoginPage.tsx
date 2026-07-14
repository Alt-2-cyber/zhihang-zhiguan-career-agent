import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowRight, BriefcaseBusiness, LockKeyhole } from 'lucide-react'
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
    <main className="min-h-screen bg-white text-slate-950">
      <header className="border-b border-slate-200 px-6 py-5 lg:px-10">
        <div className="mx-auto flex max-w-7xl items-center gap-3">
          <span className="grid size-10 place-items-center rounded-md bg-teal-700 text-white">
            <BriefcaseBusiness aria-hidden="true" size={21} strokeWidth={2} />
          </span>
          <div>
            <p className="text-base font-semibold">职航智管</p>
            <p className="text-xs text-slate-500">高校毕业生就业服务系统</p>
          </div>
        </div>
      </header>

      <section className="mx-auto grid min-h-[calc(100vh-81px)] max-w-7xl items-center px-6 py-12 lg:grid-cols-[1.1fr_0.9fr] lg:gap-20 lg:px-10">
        <div className="hidden max-w-xl lg:block">
          <h1 className="text-4xl font-semibold leading-tight text-slate-950">
            把求职建议变成
            <br />
            每天可完成的行动
          </h1>
          <p className="mt-6 max-w-lg text-base leading-8 text-slate-600">
            学生管理目标、简历、面试与投递进度，辅导员依据真实过程及时提供帮助。
          </p>
          <div className="mt-10 border-l-2 border-teal-700 pl-5 text-sm leading-7 text-slate-600">
            AI 结论均显示依据并经过人工确认，风险提醒不使用敏感属性。
          </div>
        </div>

        <div className="w-full max-w-md justify-self-center lg:justify-self-end">
          <div className="mb-8 lg:hidden">
            <h1 className="text-3xl font-semibold leading-tight">登录就业工作台</h1>
            <p className="mt-3 text-sm leading-6 text-slate-600">继续你的求职计划或班级就业管理。</p>
          </div>
          <div className="border-t-4 border-teal-700 bg-slate-50 px-6 py-8 shadow-[0_18px_60px_rgba(15,23,42,0.10)] sm:px-8">
            <div className="mb-7 flex items-center gap-3">
              <LockKeyhole aria-hidden="true" className="text-teal-700" size={22} />
              <div>
                <h2 className="text-xl font-semibold">账号登录</h2>
                <p className="mt-1 text-sm text-slate-500">学生与辅导员使用统一入口</p>
              </div>
            </div>

            <form className="space-y-5" onSubmit={handleSubmit(submit)} noValidate>
              <label className="block text-sm font-medium text-slate-700">
                账号
                <input
                  {...register('username')}
                  autoComplete="username"
                  className="mt-2 h-11 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none transition focus:border-teal-700 focus:ring-2 focus:ring-teal-700/15"
                />
                {errors.username ? <span className="mt-1 block text-xs text-red-700">{errors.username.message}</span> : null}
              </label>
              <label className="block text-sm font-medium text-slate-700">
                密码
                <input
                  {...register('password')}
                  type="password"
                  autoComplete="current-password"
                  className="mt-2 h-11 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none transition focus:border-teal-700 focus:ring-2 focus:ring-teal-700/15"
                />
                {errors.password ? <span className="mt-1 block text-xs text-red-700">{errors.password.message}</span> : null}
              </label>

              {error ? (
                <div role="alert" className="border-l-2 border-red-600 bg-red-50 px-3 py-2 text-sm text-red-800">
                  {error}
                </div>
              ) : null}

              <button
                type="submit"
                disabled={isSubmitting}
                className="flex h-11 w-full items-center justify-center gap-2 rounded-md bg-teal-700 px-4 text-sm font-semibold text-white transition hover:bg-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2 disabled:cursor-wait disabled:opacity-60"
              >
                {isSubmitting ? '正在登录' : '登录'}
                {isSubmitting ? null : <ArrowRight aria-hidden="true" size={17} />}
              </button>
            </form>
          </div>
        </div>
      </section>
    </main>
  )
}

