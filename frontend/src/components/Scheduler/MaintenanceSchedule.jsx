import { useState, useEffect } from "react";
import "./MaintenanceScheduleCalendar.css";
import ScheduleEntry from "./ScheduleEntry";

export default function MaintenanceScheduleCalendar({ maintenanceSchedules, loading, error }) {
    const [nearestMaintenanceDates, setNearestMaintenanceDates] = useState([]);

    useEffect(() => {
        // This effect runs whenever maintenanceSchedules changes
        if (maintenanceSchedules && maintenanceSchedules.length > 0) {
            const upcomingDates = getUpcomingMaintenanceDates(maintenanceSchedules);
            setNearestMaintenanceDates(upcomingDates);
        }
    }, [maintenanceSchedules]);

    function getUpcomingMaintenanceDates(schedules) {
        const now = new Date();

        // Calculate the cutoff date 7 days from now
        const nextWeek = new Date();
        nextWeek.setDate(now.getDate() + 7);

        return (schedules
            .filter((schedule) => {
                const scheduleDate = new Date(schedule.scheduled_start_time);
                // Must be between right now and 7 days from now
                return scheduleDate >= now && scheduleDate <= nextWeek;
            })
            .sort((a, b) => new Date(a.scheduled_start_time) - new Date(b.scheduled_start_time))
            .slice(0, 5)
        );
    }

    return (
        <section className="panel" aria-labelledby="maintenance-heading">
            <h2 className="section-heading panel-heading">Maintenance Schedule</h2>

            {loading && <p>Loading...</p>}
            {error && <p className="error scheduler-msg">Unable to display equipment maintenance schedules: {error}</p>}
            {!loading && !error && maintenanceSchedules.length === 0 && <p className="scheduler-msg">No maintenance events scheduled.</p>}

            {!loading && !error && maintenanceSchedules.length > 0 && (
                <div>
                    <div className="upcoming-section">
                        <h3 className="section-subheader">Upcoming</h3>
                        <p className="">{nearestMaintenanceDates.length} {nearestMaintenanceDates.length === 1 ? 'event' : 'events'}</p>
                    </div>

                    <ul>
                        {nearestMaintenanceDates.map((item, index) => (
                            <li key={index}>
                                <ScheduleEntry schedule={item} />
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </section>
    )
}