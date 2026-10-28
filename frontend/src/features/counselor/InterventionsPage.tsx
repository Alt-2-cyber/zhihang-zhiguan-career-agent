import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Plus } from "lucide-react";
import { useState } from "react";

import { apiFetch } from "../../app/api";
import {
  EmptyState,
  Notice,
  PageHeader,
  Panel,
  inputClass,
  primaryButton,
  secondaryButton,
} from "../../components/Ui";
import type { CounselorData } from "./CounselorDashboard";
import { AskAgentButton } from "../chat/AskAgentButton";

type Intervention = {
  id: string;
  student_id: string;
  title: string;
  description: string;
  status: string;
  feedback: string | null;
};

const statusLabels: Record<string, string> = {
  assigned: "待学生完成",
  acknowledged: "学生已接收",
  submitted: "待确认",
  resolved: "已完成",
  cancelled: "已取消",
};

export function InterventionsPage({ token }: { token: string }) {
  const queryClient = useQueryClient();
  const [studentId, setStudentId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const dashboard = useQuery({
    queryKey: ["counselor-dashboard"],
    queryFn: () => apiFetch<CounselorData>("/dashboard/counselor", {}, token),
  });
  const interventions = useQuery({
    queryKey: ["interventions"],
    queryFn: () => apiFetch<Intervention[]>("/interventions", {}, token),
  });
  const create = useMutation({
    mutationFn: () =>
      apiFetch(
        "/interventions",
        {
          method: "POST",
          body: JSON.stringify({ student_id: studentId, title, description }),
        },
        token,
      ),
    onSuccess: () => {
      setTitle("");
      setDescription("");
      queryClient.invalidateQueries({ queryKey: ["interventions"] });
    },
  });
  const resolve = useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/interventions/${id}/resolve`, { method: "PATCH" }, token),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["interventions"] }),
  });
  const names = new Map(
    dashboard.data?.students.map((student) => [
      student.id,
      student.display_name,
    ]),
  );
  return (
    <>
      <PageHeader
        title="帮扶任务"
        description="将风险事实转化为明确任务，学生提交反馈后由辅导员确认完成。"
      />
      <div className="grid gap-6 xl:grid-cols-[0.75fr_1.25fr]">
        <Panel title="新建帮扶任务">
          <div className="space-y-4">
            <label className="block text-sm font-medium">
              学生
              <select
                className={inputClass}
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
              >
                <option value="">选择学生</option>
                {dashboard.data?.students.map((student) => (
                  <option key={student.id} value={student.id}>
                    {student.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium">
              任务名称
              <input
                className={inputClass}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            <label className="block text-sm font-medium">
              完成要求
              <textarea
                rows={4}
                className={inputClass}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </label>
            <button
              className={`${primaryButton} w-full`}
              disabled={!studentId || !title || !description}
              onClick={() => create.mutate()}
            >
              <Plus size={16} />
              布置任务
            </button>
          </div>
        </Panel>
        <Panel title="任务进展">
          {interventions.data?.length ? (
            <div className="divide-y divide-slate-200">
              {interventions.data.map((item) => (
                <article key={item.id} className="py-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-xs text-slate-500">
                        {names.get(item.student_id) ?? "学生"}
                      </p>
                      <h3 className="mt-1 text-sm font-semibold">
                        {item.title}
                      </h3>
                      <p className="mt-2 text-sm leading-6 text-slate-600">
                        {item.description}
                      </p>
                    </div>
                    <span className="text-xs text-slate-500">
                      {statusLabels[item.status] ?? item.status}
                    </span>
                  </div>
                  <AskAgentButton role="counselor" context={{ type: "student", id: item.student_id }} className="mt-3 h-8 px-2 text-xs" />
                  {item.feedback ? (
                    <div className="mt-3">
                      <Notice tone="info">学生反馈：{item.feedback}</Notice>
                    </div>
                  ) : null}
                  {item.status === "submitted" ? (
                    <button
                      className={`${secondaryButton} mt-3`}
                      onClick={() => resolve.mutate(item.id)}
                    >
                      <CheckCircle2 size={16} />
                      确认完成
                    </button>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              title="还没有帮扶任务"
              description="选择需要帮助的学生并布置一个可验证的任务。"
            />
          )}
        </Panel>
      </div>
    </>
  );
}
