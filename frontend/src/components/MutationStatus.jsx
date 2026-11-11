export default function MutationStatus({action}) {
  return <><p role="status">{action.busy ? 'Saving…' : action.message}</p>{action.error && <p role="alert" className="error">{action.error}</p>}</>
}

