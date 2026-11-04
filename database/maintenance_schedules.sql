CREATE TABLE IF NOT EXISTS maintenance_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id UUID NOT NULL REFERENCES equipment(equipment_id) ON DELETE CASCADE,
    
    -- Time windows
    scheduled_start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    scheduled_end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    
    -- Lifecycle
    status VARCHAR(30) DEFAULT 'pending',
    priority_score INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_schedule_equipment_id ON maintenance_schedules(equipment_id);
CREATE INDEX idx_schedule_time_range ON maintenance_schedules(scheduled_start_time, scheduled_end_time);
CREATE INDEX idx_schedule_status ON maintenance_schedules(status);

CREATE UNIQUE INDEX idx_unique_active_equipment_schedule 
ON maintenance_schedules (equipment_id) 
WHERE status IN ('pending', 'scheduled');