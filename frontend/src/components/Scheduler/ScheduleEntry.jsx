export default function ScheduleEntry({ schedule }) {
    const { asset_tag, scheduled_start_time, scheduled_end_time, status, priority_score } = schedule;

    function formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
    }

    function formatTime(dateString) {
        const date = new Date(dateString);
        return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    }

    return (
        <section className="panel schedule-entry">
            <p style={{ fontWeight: 'bold', margin: 0 }}>{asset_tag}</p>
            <p style={{ margin: 0 }}>{formatDate(scheduled_start_time)} {formatTime(scheduled_start_time)} - {formatTime(scheduled_end_time)}</p>
        </section>
    )
}