export default function ScheduleEntry({ schedule }) {
    const { asset_tag, scheduled_start_time, scheduled_end_time, status, status_msg, priority_score } = schedule;

    let assetTagColor = ''
    if (status === "scheduled")
        assetTagColor = "#99e499";
    else if (status === "incomplete")
        assetTagColor = "#ff7070";

    function formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
    }

    function formatTime(dateString) {
        const date = new Date(dateString);
        return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
    }

    return (
        <section className="panel schedule-entry" style={{ padding: "12px" }}>
            <p style={{ fontWeight: 'bold', margin: 0, color: assetTagColor }}>{asset_tag}</p>
            <p>{formatDate(scheduled_start_time)} {formatTime(scheduled_start_time)} - {formatTime(scheduled_end_time)}</p>
            <p>{status_msg}</p>
        </section>
    )
}