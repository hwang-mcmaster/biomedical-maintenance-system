const paths={
 overview:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
 equipment:'M4 4h16v13H4z M8 21h8 M12 17v4 M7 11h3l2-4 2 7 2-3h2',
 tasks:'M8 4H5v17h14V4h-3 M9 2h6v4H9z M8 11h8 M8 15h6',
 scheduling:'M4 5h16v16H4z M8 2v6 M16 2v6 M4 10h16 M8 14h2 M14 14h2 M8 17h2',
 technicians:'M9 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M2 21v-3a6 6 0 0 1 12 0v3 M17 4a4 4 0 0 1 0 8 M18 15a5 5 0 0 1 4 5',
 'my-work':'M9 3h6v4H9z M7 5H4v16h16V5h-3 M8 13l3 3 5-6',
 administration:'M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6z M9 12l2 2 4-4',
 advanced:'M4 6h16 M4 12h16 M4 18h16 M8 3v6 M16 9v6 M10 15v6',
 plus:'M12 5v14 M5 12h14'
}
export default function NavigationIcon({name}){return <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]||paths.plus}/></svg>}
