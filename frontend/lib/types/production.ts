export type ProductionStatus = "draft" | "active_eligible" | "archived";

export type Production = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  status: ProductionStatus;
  created_at: string;
  updated_at: string;
  archived_at: string | null;
};

export type ActiveProduction = {
  production_id: string | null;
  production: Production | null;
};

export type ProductionCreateInput = {
  name: string;
  slug?: string;
  description?: string;
};
