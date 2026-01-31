TITLES_QUERY = """
query Titles {
  titles { id name }
}
"""

TEAMS_QUERY_BASIC = """
query Teams($q: String!) {
  teams(filter: { name: { contains: $q } }) {
    edges { node { id name } }
  }
}
"""

TEAMS_QUERY_EXTENDED = """
query Teams($q: String!) {
  teams(filter: { name: { contains: $q } }) {
    edges { node { id name abbreviation shortName } }
  }
}
"""

TOURNAMENTS_QUERY = """
query Tournaments($titleId: ID!, $first: Int!, $after: Cursor) {
  tournaments(
    filter: { title: { id: { in: [$titleId] } } }
    first: $first
    after: $after
  ) {
    totalCount
    edges { cursor node { id name } }
    pageInfo { endCursor hasNextPage }
  }
}
"""

ALL_SERIES_QUERY = """
query AllSeries($tournamentIds: [ID!]!, $gte: String!, $lte: String!, $first: Int!, $after: Cursor) {
  allSeries(
    filter: {
      tournament: { id: { in: $tournamentIds }, includeChildren: { equals: true } }
      startTimeScheduled: { gte: $gte, lte: $lte }
    }
    orderBy: StartTimeScheduled
    first: $first
    after: $after
  ) {
    totalCount
    edges {
      cursor
      node {
        id
        startTimeScheduled
        tournament { id name }
        teams { baseInfo { id name } }
      }
    }
    pageInfo { endCursor hasNextPage }
  }
}
"""

SERIES_STATE_QUERY_BASIC = """
query SeriesState($id: ID!) {
  seriesState(id: $id) {
    valid
    finished
    startedAt
    teams {
      id
      name
      won
      score
      kills
      deaths
    }
    games {
      sequenceNumber
      teams {
        id
        won
        score
        kills
        deaths
        players {
          id
          name
          kills
          deaths
        }
      }
    }
  }
}
"""

# Extended fields for best-effort character extraction. If the schema
# doesn't support these fields, callers should fall back to the BASIC query.
SERIES_STATE_QUERY_CHARACTER = """
query SeriesState($id: ID!) {
  seriesState(id: $id) {
    valid
    finished
    startedAt
    teams {
      id
      name
      won
      score
      kills
      deaths
    }
    games {
      sequenceNumber
      teams {
        id
        won
        score
        kills
        deaths
        players {
          id
          name
          kills
          deaths
          character { id name }
        }
      }
    }
  }
}
"""
