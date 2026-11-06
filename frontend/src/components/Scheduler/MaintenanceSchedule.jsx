import { useState, useEffect } from "react";
import "./MaintenanceScheduleCalendar.css";
import ScheduleEntry from "./ScheduleEntry";
import Calendar from "./Calendar";

export default function MaintenanceScheduleCalendar({ maintenanceSchedules, loading, error }) {
    const [scheduledMaintenanceDates, setScheduledMaintenanceDates] = useState([]);
    const [nearestMaintenanceDates, setNearestMaintenanceDates] = useState([]);
    const [incompleteMaintenanceDates, setIncompleteMaintenanceDates] = useState([]);
    const [calendarSelectedAssetTag, setCalendarSelectedAssetTag] = useState("");

    useEffect(() => {
        if (maintenanceSchedules && maintenanceSchedules.length > 0) {
            const scheduledDates = maintenanceSchedules.filter((schedule) => schedule.status === "scheduled");
            setScheduledMaintenanceDates(scheduledDates)

            const upcomingDates = getUpcomingMaintenanceDates(scheduledDates);
            setNearestMaintenanceDates(upcomingDates);

            const incompleteDates = getIncompleteMaintenanceDates(maintenanceSchedules);
            setIncompleteMaintenanceDates(incompleteDates);
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

    function getIncompleteMaintenanceDates(schedules) {
        return (schedules
            .filter((schedule) => {
                return schedule.status === "incomplete";
            })
            .sort((a, b) => new Date(a.scheduled_start_time) - new Date(b.scheduled_start_time))
            .slice(0, 5)
        );
    }

    return (
        <section className="panel" aria-labelledby="maintenance-heading">
            <h2 className="section-heading panel-heading">Maintenance Schedule</h2>

            <Calendar
                maintenanceSchedules={maintenanceSchedules.filter((schedule) => schedule.status !== "pending") || []}
                onSelectSchedule={(assetTag) => setCalendarSelectedAssetTag(assetTag)}
            />

            {loading && <p>Loading...</p>}
            {error && <p className="error scheduler-msg">Unable to display equipment maintenance schedules: {error}</p>}
            {!loading && !error && maintenanceSchedules.length === 0 && <p className="scheduler-msg">No maintenance events scheduled.</p>}

            {!loading && !error && nearestMaintenanceDates.length > 0 && (
                <div>
                    <div className="upcoming-section">
                        <h3 className="section-subheader">Upcoming</h3>
                        <p className="perfect-circle" style={{ backgroundColor: "#99e499" }}>{nearestMaintenanceDates.length}</p>
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

            {!loading && !error && incompleteMaintenanceDates.length > 0 && (
                <div>
                    <div className="incomplete-section">
                        <h3 className="section-subheader">Incomplete</h3>
                        <p className="perfect-circle" style={{ backgroundColor: "#ff7070" }}>{incompleteMaintenanceDates.length}</p>
                    </div>

                    <ul>
                        {incompleteMaintenanceDates.map((item, index) => (
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