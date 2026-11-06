import React from 'react';
import { useState } from 'react';

import FullCalendar from '@fullcalendar/react';
import themePlugin from "@fullcalendar/react/themes/forma";
import dayGridPlugin from '@fullcalendar/react/daygrid';

import '@fullcalendar/react/skeleton.css';
import '@fullcalendar/react/themes/forma/theme.css';
import '@fullcalendar/react/themes/forma/palettes/blue.css';

export default function Calendar({ maintenanceSchedules, onSelectSchedule }) {
    const [mouseHoveredEvent, setMouseHoveredEvent] = useState(null);
    const [toolTipPosition, setToolTipPosition] = useState({ x: 0, y: 0 })


    const formattedEvents = maintenanceSchedules.map((item) => {
        let eventClassName = `${item.status}-event`

        return {
            title: item.asset_tag,
            start: item.scheduled_start_time,
            end: item.scheduled_end_time,
            color:
                item.status === 'completed' ? '#99b6e4' :
                    item.status === 'scheduled' ? '#99e499' :
                        item.status === 'incomplete' ? '#ff7070' :
                            '#ffd58b',
            extendedProps: {
                status: item.status,
                priority: item.priority_score || '0',
            }
        }
    });

    const handleEventClick = (clickInfo) => {
        onSelectSchedule(clickInfo.event.id);
    };

    const handleEventMouseEnter = (mouseEnterInfo) => { };

    const handleEventMouseLeave = () => {
        setMouseHoveredEvent(null)
    }

    return (
        <div className="calendar-container" style={{ margin: "2rem 0 2rem 0" }}>
            <FullCalendar
                plugins={[themePlugin, dayGridPlugin]}
                initialView="dayGridMonth"
                headerToolbar={{
                    start: 'title',
                    end: 'today,prev,next',
                }}
                editable={false}
                selectable={false}
                displayEventTime={false}
                events={formattedEvents}
                eventClick={handleEventClick}
                eventMouseEnter={handleEventMouseEnter}
                eventMouseLeave={handleEventMouseLeave}
                height="auto"
            />
        </div>
    )
}