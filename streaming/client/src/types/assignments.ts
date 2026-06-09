export type TAssignmentStepStatus = "pending" | "in_progress" | "done";

export type TStepActionType = "navigate" | "focus_element" | "none";

export type TStepButton = {
  text: string;
  action_type: TStepActionType;
  action_target: string | null;
};

export type TAssignmentStep = {
  id: string;
  title: string;
  description: string;
  order: number;
  status: TAssignmentStepStatus;
  route: string | null;
  button: TStepButton | null;
  app_url: string | null;
  help_topic_id: string | null;
  completed_at: string | null;
};

export type TAssignmentMetadata = {
  version: number;
  steps: TAssignmentStep[];
};

export type TUserAssignment = {
  id: string;
  key: string | null;
  title: string;
  status: "pending" | "in_progress" | "done" | "archived";
  organization_id: string | null;
  metadata: TAssignmentMetadata;
  progress: number;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type TUserAssignmentsListResponse = {
  assignments: TUserAssignment[];
};
