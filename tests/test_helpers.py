import datetime
from scripts.utils import helpers

def test_parse_file_name_properties():
    pf = helpers.ParseFileName('2024-01-15_01:02:03.wav')
    assert pf.iso8601.startswith('2024-01-15T01:02:03')
    assert pf.week == datetime.datetime(2024, 1, 15).isocalendar()[1]
    assert pf.RTSP_id == ""


def test_detection_attributes():
    file_date = datetime.datetime(2024, 1, 15, 0, 0, 0)
    det = helpers.Detection(file_date, 0, 3, 'Testus species_Sample Bird', 0.95)
    assert det.date == '2024-01-15'
    assert det.time == '00:00:00'
    assert det.week == file_date.isocalendar()[1]
    assert det.common_name == 'Sample Bird'
    assert det.scientific_name == 'Testus species'
    assert det.common_name_safe == 'Sample_Bird'
    assert det.confidence == 0.95
    assert det.confidence_pct == 95


def test_get_font_default(mocker):
    mocker.patch('scripts.utils.helpers.get_settings', return_value={'DATABASE_LANG': 'en'})
    font = helpers.get_font()
    assert font['font.family'] == 'Roboto Flex'
    assert font['path'].endswith('RobotoFlex-Regular.ttf')


def test_get_font_arabic(mocker):
    mocker.patch('scripts.utils.helpers.get_settings', return_value={'DATABASE_LANG': 'ar'})
    font = helpers.get_font()
    assert font['font.family'] == 'Noto Sans Arabic'
    assert font['path'].endswith('NotoSansArabic-Regular.ttf')
