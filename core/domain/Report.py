from core.domain.Team import Team


class Report:
    def __init__(self, report_id:int, current_team:Team, opponent_team:Team):
        self.report_id = report_id
        self.current_team = current_team
        self.opponent_team = opponent_team