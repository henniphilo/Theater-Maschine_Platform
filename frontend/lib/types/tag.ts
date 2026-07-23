export type Tag = {
  id: string;
  production_id: string;
  name: string;
  created_at: string;
  updated_at: string;
};

export type TagCreateInput = {
  production_id: string;
  name: string;
};
