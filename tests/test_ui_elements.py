"""Tests for data/ui_elements.py — UI Dictionary content."""

from data.ui_elements import UI_ELEMENTS, get_elements_by_category, get_element_names


class TestUIElements:
    def test_has_20_elements(self):
        assert len(UI_ELEMENTS) == 22  # 6 layout + 6 interactive + 6 content + 4 form

    def test_all_have_required_fields(self):
        for el in UI_ELEMENTS:
            assert el.name, f"Missing name"
            assert el.category in ("layout", "interactive", "content", "form"), \
                f"{el.name}: bad category {el.category}"
            assert el.wireframe, f"{el.name}: missing wireframe"
            assert el.desc_en, f"{el.name}: missing desc_en"
            assert el.desc_ua, f"{el.name}: missing desc_ua"
            assert el.prompt_en, f"{el.name}: missing prompt_en"
            assert el.prompt_ua, f"{el.name}: missing prompt_ua"

    def test_categories(self):
        by_cat = get_elements_by_category()
        assert "layout" in by_cat
        assert "interactive" in by_cat
        assert "content" in by_cat
        assert "form" in by_cat
        assert len(by_cat["layout"]) >= 5

    def test_element_names(self):
        names = get_element_names()
        assert len(names) == len(UI_ELEMENTS)
        assert "Navbar / Navigation Bar" in names
        assert "Modal / Dialog / Popup" in names
        assert "Button" in names

    def test_wireframes_are_ascii(self):
        for el in UI_ELEMENTS:
            # Should be printable ASCII + basic unicode
            assert len(el.wireframe) > 10, f"{el.name}: wireframe too short"
