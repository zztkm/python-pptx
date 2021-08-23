# encoding: utf-8

"""Unit-test suite for `pptx.opc.package` module."""

import io

import pytest

from pptx.opc.constants import CONTENT_TYPE as CT, RELATIONSHIP_TYPE as RT
from pptx.opc.oxml import CT_Relationships
from pptx.opc.packuri import PACKAGE_URI, PackURI
from pptx.opc.package import (
    OpcPackage,
    Part,
    PartFactory,
    _Relationship,
    _Relationships,
    Unmarshaller,
    XmlPart,
)
from pptx.opc.serialized import PackageReader
from pptx.oxml.xmlchemy import BaseOxmlElement
from pptx.package import Package

from ..unitutil.cxml import element
from ..unitutil.file import absjoin, test_file_dir
from ..unitutil.mock import (
    call,
    class_mock,
    cls_attr_mock,
    function_mock,
    initializer_mock,
    instance_mock,
    loose_mock,
    method_mock,
    Mock,
    patch,
    property_mock,
    PropertyMock,
)


class DescribeOpcPackage(object):
    """Unit-test suite for `pptx.opc.package.OpcPackage` objects."""

    def it_can_open_a_pkg_file(self, PackageReader_, PartFactory_, Unmarshaller_):
        # mockery ----------------------
        pkg_file = Mock(name="pkg_file")
        pkg_reader = PackageReader_.from_file.return_value
        # exercise ---------------------
        pkg = OpcPackage.open(pkg_file)
        # verify -----------------------
        PackageReader_.from_file.assert_called_once_with(pkg_file)
        Unmarshaller_.unmarshal.assert_called_once_with(pkg_reader, pkg, PartFactory_)
        assert isinstance(pkg, OpcPackage)

    def it_can_add_a_relationship_to_a_part(self, request, _rels_prop_, relationships_):
        _rels_prop_.return_value = relationships_
        relationship_ = instance_mock(request, _Relationship)
        relationships_.add_relationship.return_value = relationship_
        target_ = instance_mock(request, Part, name="target_part")
        package = OpcPackage()

        relationship = package.load_rel(RT.SLIDE, target_, "rId99")

        relationships_.add_relationship.assert_called_once_with(
            RT.SLIDE, target_, "rId99", False
        )
        assert relationship is relationship_

    def it_can_establish_a_relationship_to_another_part(
        self, request, _rels_prop_, relationships_
    ):
        _rels_prop_.return_value = relationships_
        relationship_ = instance_mock(request, _Relationship)
        relationships_.get_or_add.return_value = relationship_
        relationship_.rId = "rId99"
        part_ = instance_mock(request, Part)
        package = OpcPackage()

        rId = package.relate_to(part_, "http://rel/type")

        relationships_.get_or_add.assert_called_once_with("http://rel/type", part_)
        assert rId == "rId99"

    def it_can_provide_a_list_of_the_parts_it_contains(self):
        # mockery ----------------------
        parts = [Mock(name="part1"), Mock(name="part2")]
        pkg = OpcPackage()
        # verify -----------------------
        with patch.object(OpcPackage, "iter_parts", return_value=parts):
            assert pkg.parts == [parts[0], parts[1]]

    def it_can_iterate_over_its_parts(self, iter_parts_fixture):
        package, expected_parts = iter_parts_fixture
        parts = list(package.iter_parts())
        assert parts == expected_parts

    def it_can_iterate_over_its_relationships(self, iter_rels_fixture):
        package, expected_rels = iter_rels_fixture
        rels = list(package.iter_rels())
        assert rels == expected_rels

    def it_can_find_a_part_related_by_reltype(
        self, request, _rels_prop_, relationships_
    ):
        related_part_ = instance_mock(request, Part, name="related_part_")
        relationships_.part_with_reltype.return_value = related_part_
        _rels_prop_.return_value = relationships_
        package = OpcPackage()

        related_part = package.part_related_by(RT.SLIDE)

        relationships_.part_with_reltype.assert_called_once_with(RT.SLIDE)
        assert related_part is related_part_

    def it_can_find_the_next_available_vector_partname(self, next_partname_fixture):
        package, partname_template, expected_partname = next_partname_fixture
        partname = package.next_partname(partname_template)
        assert isinstance(partname, PackURI)
        assert partname == expected_partname

    def it_can_save_to_a_pkg_file(self, request, _rels_prop_, rels_):
        PackageWriter_ = class_mock(request, "pptx.opc.package.PackageWriter")
        _rels_prop_.return_value = rels_
        property_mock(request, OpcPackage, "parts", return_value=["parts"])
        package = OpcPackage()

        package.save("prs.pptx")

        PackageWriter_.write.assert_called_once_with("prs.pptx", rels_, ["parts"])

    def it_constructs_its_relationships_object_to_help(self, request, relationships_):
        _Relationships_ = class_mock(
            request, "pptx.opc.package._Relationships", return_value=relationships_
        )
        package = OpcPackage()

        rels = package._rels

        _Relationships_.assert_called_once_with(PACKAGE_URI.baseURI)
        assert rels is relationships_

    # fixtures ---------------------------------------------

    @pytest.fixture
    def iter_parts_fixture(self, request, rels_fixture):
        package, parts, rels = rels_fixture
        expected_parts = list(parts)
        return package, expected_parts

    @pytest.fixture
    def iter_rels_fixture(self, request, rels_fixture):
        package, parts, rels = rels_fixture
        expected_rels = list(rels)
        return package, expected_rels

    @pytest.fixture(params=[((), 1), ((1,), 2), ((1, 2), 3), ((2, 3), 1), ((1, 3), 2)])
    def next_partname_fixture(self, request, iter_parts_):
        existing_partname_numbers, next_partname_number = request.param
        package = OpcPackage()
        parts = [
            instance_mock(
                request, Part, name="part[%d]" % idx, partname="/foo/bar/baz%d.xml" % n
            )
            for idx, n in enumerate(existing_partname_numbers)
        ]
        iter_parts_.return_value = iter(parts)
        partname_template = "/foo/bar/baz%d.xml"
        expected_partname = PackURI("/foo/bar/baz%d.xml" % next_partname_number)
        return package, partname_template, expected_partname

    @pytest.fixture
    def rels_fixture(self, request, _rels_prop_, part_1_, part_2_):
        """
        +----------+          +--------+
        | pkg_rels |-- r1 --> | part_1 |
        +----------+          +--------+
             |     |            |    ^
          r5 |     | r4      r2 |    | r3
             |     |            |    |
             v     |            v    |
         external  |          +--------+
                   +--------> | part_2 |
                              +--------+
        """
        r1 = self.rel(request, False, part_1_, "r1")
        r2 = self.rel(request, False, part_2_, "r2")
        r3 = self.rel(request, False, part_1_, "r3")
        r4 = self.rel(request, False, part_2_, "r4")
        r5 = self.rel(request, True, None, "r5")

        package = OpcPackage()

        _rels_prop_.return_value = self.rels(request, (r1, r4, r5))
        part_1_.rels = self.rels(request, (r2,))
        part_2_.rels = self.rels(request, (r3,))

        return package, (part_1_, part_2_), (r1, r2, r3, r4, r5)

    # fixture components -----------------------------------

    @pytest.fixture
    def iter_parts_(self, request):
        return method_mock(request, OpcPackage, "iter_parts")

    @pytest.fixture
    def PackageReader_(self, request):
        return class_mock(request, "pptx.opc.package.PackageReader")

    @pytest.fixture
    def PartFactory_(self, request):
        return class_mock(request, "pptx.opc.package.PartFactory")

    @pytest.fixture
    def part_1_(self, request):
        return instance_mock(request, Part)

    @pytest.fixture
    def part_2_(self, request):
        return instance_mock(request, Part)

    def rel(self, request, is_external, target_part, name):
        return instance_mock(
            request,
            _Relationship,
            is_external=is_external,
            target_part=target_part,
            name=name,
        )

    @pytest.fixture
    def relationships_(self, request):
        return instance_mock(request, _Relationships)

    def rels(self, request, values):
        rels = instance_mock(request, _Relationships)
        rels.values.return_value = values
        return rels

    @pytest.fixture
    def rels_(self, request):
        return instance_mock(request, _Relationships)

    @pytest.fixture
    def _rels_prop_(self, request):
        return property_mock(request, OpcPackage, "_rels")

    @pytest.fixture
    def Unmarshaller_(self, request):
        return class_mock(request, "pptx.opc.package.Unmarshaller")


class DescribePart(object):
    """Unit-test suite for `pptx.opc.package.Part` objects."""

    def it_can_be_constructed_by_PartFactory(self, request, package_):
        partname_ = PackURI("/ppt/slides/slide1.xml")
        _init_ = initializer_mock(request, Part)

        part = Part.load(partname_, CT.PML_SLIDE, b"blob", package_)

        _init_.assert_called_once_with(part, partname_, CT.PML_SLIDE, b"blob", package_)
        assert isinstance(part, Part)

    def it_uses_the_load_blob_as_its_blob(self, blob_fixture):
        part, load_blob = blob_fixture
        assert part.blob is load_blob

    def it_can_change_its_blob(self):
        part, new_blob = Part(None, None, "xyz", None), "foobar"
        part.blob = new_blob
        assert part.blob == new_blob

    def it_knows_its_content_type(self, content_type_fixture):
        part, expected_content_type = content_type_fixture
        assert part.content_type == expected_content_type

    @pytest.mark.parametrize("ref_count, calls", ((2, []), (1, [call("rId42")])))
    def it_can_drop_a_relationship(
        self, request, _rels_prop_, relationships_, ref_count, calls
    ):
        _rel_ref_count_ = method_mock(
            request, Part, "_rel_ref_count", return_value=ref_count
        )
        _rels_prop_.return_value = relationships_
        part = Part(None, None, None)

        part.drop_rel("rId42")

        _rel_ref_count_.assert_called_once_with(part, "rId42")
        assert relationships_.pop.call_args_list == calls

    def it_can_load_a_relationship(self, load_rel_fixture):
        part, rels_, reltype_, target_, rId_ = load_rel_fixture

        part.load_rel(reltype_, target_, rId_)

        rels_.add_relationship.assert_called_once_with(reltype_, target_, rId_, False)

    def it_knows_the_package_it_belongs_to(self, package_get_fixture):
        part, expected_package = package_get_fixture
        assert part.package == expected_package

    def it_can_find_a_related_part_by_reltype(self, related_part_fixture):
        part, reltype_, related_part_ = related_part_fixture

        related_part = part.part_related_by(reltype_)

        part.rels.part_with_reltype.assert_called_once_with(reltype_)
        assert related_part is related_part_

    def it_knows_its_partname(self, partname_get_fixture):
        part, expected_partname = partname_get_fixture
        assert part.partname == expected_partname

    def it_can_change_its_partname(self, partname_set_fixture):
        part, new_partname = partname_set_fixture
        part.partname = new_partname
        assert part.partname == new_partname

    def it_can_establish_a_relationship_to_another_part(self, relate_to_part_fixture):
        part, target_, reltype_, rId_ = relate_to_part_fixture

        rId = part.relate_to(target_, reltype_)

        part.rels.get_or_add.assert_called_once_with(reltype_, target_)
        assert rId is rId_

    def it_can_establish_an_external_relationship(self, relate_to_url_fixture):
        part, url_, reltype_, rId_ = relate_to_url_fixture

        rId = part.relate_to(url_, reltype_, is_external=True)

        part.rels.get_or_add_ext_rel.assert_called_once_with(reltype_, url_)
        assert rId is rId_

    def it_can_find_a_related_part_by_rId(
        self, request, _rels_prop_, relationships_, relationship_, part_
    ):
        relationship_.target_part = part_
        relationships_.__getitem__.return_value = relationship_
        _rels_prop_.return_value = relationships_
        part = Part(None, None, None)

        related_part = part.related_part("rId17")

        relationships_.__getitem__.assert_called_once_with("rId17")
        assert related_part is part_

    def it_provides_access_to_its_relationships(self, rels_fixture):
        part, Relationships_, partname_, rels_ = rels_fixture

        rels = part.rels

        Relationships_.assert_called_once_with(partname_.baseURI)
        assert rels is rels_

    def it_can_find_the_uri_of_an_external_relationship(self, target_ref_fixture):
        part, rId_, url_ = target_ref_fixture

        url = part.target_ref(rId_)

        assert url == url_

    def it_can_load_a_blob_from_a_file_path_to_help(self):
        path = absjoin(test_file_dir, "minimal.pptx")
        with open(path, "rb") as f:
            file_bytes = f.read()
        part = Part(None, None, None, None)

        assert part._blob_from_file(path) == file_bytes

    def it_can_load_a_blob_from_a_file_like_object_to_help(self):
        part = Part(None, None, None, None)
        assert part._blob_from_file(io.BytesIO(b"012345")) == b"012345"

    # fixtures ---------------------------------------------

    @pytest.fixture
    def blob_fixture(self, blob_):
        part = Part(None, None, blob_, None)
        return part, blob_

    @pytest.fixture
    def content_type_fixture(self):
        content_type = "content/type"
        part = Part(None, content_type, None, None)
        return part, content_type

    @pytest.fixture
    def load_rel_fixture(self, part, _rels_prop_, rels_, reltype_, part_, rId_):
        _rels_prop_.return_value = rels_
        return part, rels_, reltype_, part_, rId_

    @pytest.fixture
    def package_get_fixture(self, package_):
        part = Part(None, None, None, package_)
        return part, package_

    @pytest.fixture
    def partname_get_fixture(self):
        partname = PackURI("/part/name")
        part = Part(partname, None, None, None)
        return part, partname

    @pytest.fixture
    def partname_set_fixture(self):
        old_partname = PackURI("/old/part/name")
        new_partname = PackURI("/new/part/name")
        part = Part(old_partname, None, None, None)
        return part, new_partname

    @pytest.fixture
    def relate_to_part_fixture(self, part, _rels_prop_, reltype_, part_, rels_, rId_):
        _rels_prop_.return_value = rels_
        target_ = part_
        return part, target_, reltype_, rId_

    @pytest.fixture
    def relate_to_url_fixture(self, part, _rels_prop_, rels_, url_, reltype_, rId_):
        _rels_prop_.return_value = rels_
        return part, url_, reltype_, rId_

    @pytest.fixture
    def related_part_fixture(self, part, _rels_prop_, rels_, reltype_, part_):
        _rels_prop_.return_value = rels_
        return part, reltype_, part_

    @pytest.fixture
    def rels_fixture(self, Relationships_, partname_, rels_):
        part = Part(partname_, None)
        return part, Relationships_, partname_, rels_

    @pytest.fixture
    def target_ref_fixture(self, part, _rels_prop_, rId_, rel_, url_):
        _rels_prop_.return_value = {rId_: rel_}
        return part, rId_, url_

    # fixture components ---------------------------------------------

    @pytest.fixture
    def blob_(self, request):
        return instance_mock(request, bytes)

    @pytest.fixture
    def package_(self, request):
        return instance_mock(request, OpcPackage)

    @pytest.fixture
    def part(self):
        return Part(None, None)

    @pytest.fixture
    def part_(self, request):
        return instance_mock(request, Part)

    @pytest.fixture
    def partname_(self, request):
        return instance_mock(request, PackURI)

    @pytest.fixture
    def Relationships_(self, request, rels_):
        return class_mock(
            request, "pptx.opc.package._Relationships", return_value=rels_
        )

    @pytest.fixture
    def rel_(self, request, rId_, url_):
        return instance_mock(request, _Relationship, rId=rId_, target_ref=url_)

    @pytest.fixture
    def relationship_(self, request):
        return instance_mock(request, _Relationship)

    @pytest.fixture
    def relationships_(self, request):
        return instance_mock(request, _Relationships)

    @pytest.fixture
    def rels_(self, request, part_, rel_, rId_):
        rels_ = instance_mock(request, _Relationships)
        rels_.part_with_reltype.return_value = part_
        rels_.get_or_add.return_value = rel_
        rels_.get_or_add_ext_rel.return_value = rId_
        return rels_

    @pytest.fixture
    def _rels_prop_(self, request):
        return property_mock(request, Part, "_rels")

    @pytest.fixture
    def reltype_(self, request):
        return instance_mock(request, str)

    @pytest.fixture
    def rId_(self, request):
        return instance_mock(request, str)

    @pytest.fixture
    def url_(self, request):
        return instance_mock(request, str)


class DescribeXmlPart(object):
    """Unit-test suite for `pptx.opc.package.XmlPart` objects."""

    def it_can_be_constructed_by_PartFactory(self, request):
        partname = PackURI("/ppt/slides/slide1.xml")
        element_ = element("p:sld")
        package_ = instance_mock(request, OpcPackage)
        parse_xml_ = function_mock(
            request, "pptx.opc.package.parse_xml", return_value=element_
        )
        _init_ = initializer_mock(request, XmlPart)

        part = XmlPart.load(partname, CT.PML_SLIDE, b"blob", package_)

        parse_xml_.assert_called_once_with(b"blob")
        _init_.assert_called_once_with(part, partname, CT.PML_SLIDE, element_, package_)
        assert isinstance(part, XmlPart)

    def it_can_serialize_to_xml(self, blob_fixture):
        xml_part, element_, serialize_part_xml_ = blob_fixture
        blob = xml_part.blob
        serialize_part_xml_.assert_called_once_with(element_)
        assert blob is serialize_part_xml_.return_value

    def it_knows_its_the_part_for_its_child_objects(self, part_fixture):
        xml_part = part_fixture
        assert xml_part.part is xml_part

    # fixtures -------------------------------------------------------

    @pytest.fixture
    def blob_fixture(self, request, element_, serialize_part_xml_):
        xml_part = XmlPart(None, None, element_, None)
        return xml_part, element_, serialize_part_xml_

    @pytest.fixture
    def part_fixture(self):
        return XmlPart(None, None, None, None)

    # fixture components ---------------------------------------------

    @pytest.fixture
    def element_(self, request):
        return instance_mock(request, BaseOxmlElement)

    @pytest.fixture
    def serialize_part_xml_(self, request):
        return function_mock(request, "pptx.opc.package.serialize_part_xml")


class DescribePartFactory(object):
    """Unit-test suite for `pptx.opc.package.PartFactory` objects."""

    def it_constructs_custom_part_type_for_registered_content_types(
        self, part_args_, CustomPartClass_, part_of_custom_type_
    ):
        # fixture ----------------------
        partname, content_type, pkg, blob = part_args_
        # exercise ---------------------
        PartFactory.part_type_for[content_type] = CustomPartClass_
        part = PartFactory(partname, content_type, pkg, blob)
        # verify -----------------------
        CustomPartClass_.load.assert_called_once_with(partname, content_type, pkg, blob)
        assert part is part_of_custom_type_

    def it_constructs_part_using_default_class_when_no_custom_registered(
        self, part_args_2_, DefaultPartClass_, part_of_default_type_
    ):
        partname, content_type, pkg, blob = part_args_2_
        part = PartFactory(partname, content_type, pkg, blob)
        DefaultPartClass_.load.assert_called_once_with(
            partname, content_type, pkg, blob
        )
        assert part is part_of_default_type_

    # fixtures ---------------------------------------------

    @pytest.fixture
    def part_of_custom_type_(self, request):
        return instance_mock(request, Part)

    @pytest.fixture
    def CustomPartClass_(self, request, part_of_custom_type_):
        CustomPartClass_ = Mock(name="CustomPartClass", spec=Part)
        CustomPartClass_.load.return_value = part_of_custom_type_
        return CustomPartClass_

    @pytest.fixture
    def part_of_default_type_(self, request):
        return instance_mock(request, Part)

    @pytest.fixture
    def DefaultPartClass_(self, request, part_of_default_type_):
        DefaultPartClass_ = cls_attr_mock(request, PartFactory, "default_part_type")
        DefaultPartClass_.load.return_value = part_of_default_type_
        return DefaultPartClass_

    @pytest.fixture
    def part_args_(self, request):
        partname_ = PackURI("/foo/bar.xml")
        content_type_ = "content/type"
        pkg_ = instance_mock(request, Package, name="pkg_")
        blob_ = b"blob_"
        return partname_, content_type_, pkg_, blob_

    @pytest.fixture
    def part_args_2_(self, request):
        partname_2_ = PackURI("/bar/foo.xml")
        content_type_2_ = "foobar/type"
        pkg_2_ = instance_mock(request, Package, name="pkg_2_")
        blob_2_ = b"blob_2_"
        return partname_2_, content_type_2_, pkg_2_, blob_2_


class Describe_Relationships(object):
    """Unit-test suite for `pptx.opc.package._Relationships` objects."""

    def it_has_a_len(self):
        rels = _Relationships(None)
        assert len(rels) == 0

    def it_has_dict_style_lookup_of_rel_by_rId(self):
        rel = Mock(name="rel", rId="foobar")
        rels = _Relationships(None)
        rels["foobar"] = rel
        assert rels["foobar"] == rel

    def it_should_raise_on_failed_lookup_by_rId(self):
        rels = _Relationships(None)
        with pytest.raises(KeyError):
            rels["barfoo"]

    def it_can_add_a_relationship(self, _Relationship_):
        baseURI, rId, reltype, target, external = (
            "baseURI",
            "rId9",
            "reltype",
            "target",
            False,
        )
        rels = _Relationships(baseURI)
        rel = rels.add_relationship(reltype, target, rId, external)
        _Relationship_.assert_called_once_with(rId, reltype, target, baseURI, external)
        assert rels[rId] == rel
        assert rel == _Relationship_.return_value

    def it_can_add_a_relationship_if_not_found(
        self, rels_with_matching_rel_, rels_with_missing_rel_
    ):

        rels, reltype, part, matching_rel = rels_with_matching_rel_
        assert rels.get_or_add(reltype, part) == matching_rel

        rels, reltype, part, new_rel = rels_with_missing_rel_
        assert rels.get_or_add(reltype, part) == new_rel

    def it_can_add_an_external_relationship(self, add_ext_rel_fixture_):
        rels, reltype, url = add_ext_rel_fixture_
        rId = rels.get_or_add_ext_rel(reltype, url)
        rel = rels[rId]
        assert rel.is_external
        assert rel.target_ref == url
        assert rel.reltype == reltype

    def it_should_return_an_existing_one_if_it_matches(
        self, add_matching_ext_rel_fixture_
    ):
        rels, reltype, url, rId = add_matching_ext_rel_fixture_
        _rId = rels.get_or_add_ext_rel(reltype, url)
        assert _rId == rId
        assert len(rels) == 1

    def it_can_find_a_related_part_by_reltype(self, rels_with_target_known_by_reltype):
        rels, reltype, known_target_part = rels_with_target_known_by_reltype
        part = rels.part_with_reltype(reltype)
        assert part is known_target_part

    def it_knows_the_next_available_rId_to_help(self, rels_with_rId_gap):
        rels, expected_next_rId = rels_with_rId_gap
        next_rId = rels._next_rId
        assert next_rId == expected_next_rId

    def it_can_compose_rels_xml(self, rels, rels_elm):
        rels.xml

        rels_elm.assert_has_calls(
            [
                call.add_rel("rId1", "http://rt-hyperlink", "http://some/link", True),
                call.add_rel("rId2", "http://rt-image", "../media/image1.png", False),
                call.xml(),
            ],
            any_order=True,
        )

    # --- fixtures -----------------------------------------

    @pytest.fixture
    def add_ext_rel_fixture_(self, reltype, url):
        rels = _Relationships(None)
        return rels, reltype, url

    @pytest.fixture
    def add_matching_ext_rel_fixture_(self, request, reltype, url):
        rId = "rId369"
        rels = _Relationships(None)
        rels.add_relationship(reltype, url, rId, is_external=True)
        return rels, reltype, url, rId

    @pytest.fixture
    def _rel_with_target_known_by_reltype(self, _rId, _reltype, _target_part, _baseURI):
        rel = _Relationship(_rId, _reltype, _target_part, _baseURI)
        return rel, _reltype, _target_part

    @pytest.fixture
    def rels_elm(self, request):
        """Return a rels_elm mock that will be returned from CT_Relationships.new()"""
        # --- create rels_elm mock with a .xml property ---
        rels_elm = Mock(name="rels_elm")
        xml = PropertyMock(name="xml")
        type(rels_elm).xml = xml
        rels_elm.attach_mock(xml, "xml")
        rels_elm.reset_mock()  # to clear attach_mock call
        # --- patch CT_Relationships to return that rels_elm ---
        patch_ = patch.object(CT_Relationships, "new", return_value=rels_elm)
        patch_.start()
        request.addfinalizer(patch_.stop)
        return rels_elm

    @pytest.fixture
    def rels_with_matching_rel_(self, request, rels):
        matching_reltype_ = instance_mock(request, str, name="matching_reltype_")
        matching_part_ = instance_mock(request, Part, name="matching_part_")
        matching_rel_ = instance_mock(
            request,
            _Relationship,
            name="matching_rel_",
            reltype=matching_reltype_,
            target_part=matching_part_,
            is_external=False,
        )
        rels[1] = matching_rel_
        return rels, matching_reltype_, matching_part_, matching_rel_

    @pytest.fixture
    def rels_with_missing_rel_(self, request, rels, _Relationship_):
        missing_reltype_ = instance_mock(request, str, name="missing_reltype_")
        missing_part_ = instance_mock(request, Part, name="missing_part_")
        new_rel_ = instance_mock(
            request,
            _Relationship,
            name="new_rel_",
            reltype=missing_reltype_,
            target_part=missing_part_,
            is_external=False,
        )
        _Relationship_.return_value = new_rel_
        return rels, missing_reltype_, missing_part_, new_rel_

    @pytest.fixture
    def rels_with_rId_gap(self, request):
        rels = _Relationships(None)

        rel_with_rId1 = instance_mock(
            request, _Relationship, name="rel_with_rId1", rId="rId1"
        )
        rel_with_rId3 = instance_mock(
            request, _Relationship, name="rel_with_rId3", rId="rId3"
        )
        rels["rId1"] = rel_with_rId1
        rels["rId3"] = rel_with_rId3
        return rels, "rId2"

    @pytest.fixture
    def rels_with_target_known_by_reltype(
        self, rels, _rel_with_target_known_by_reltype
    ):
        rel, reltype, target_part = _rel_with_target_known_by_reltype
        rels[1] = rel
        return rels, reltype, target_part

    # --- fixture components -------------------------------

    @pytest.fixture
    def _baseURI(self):
        return "/baseURI"

    @pytest.fixture
    def _Relationship_(self, request):
        return class_mock(request, "pptx.opc.package._Relationship")

    @pytest.fixture
    def rels(self):
        """
        Populated _Relationships instance that will exercise the
        rels.xml property.
        """
        rels = _Relationships("/baseURI")
        rels.add_relationship(
            reltype="http://rt-hyperlink",
            target="http://some/link",
            rId="rId1",
            is_external=True,
        )
        part = Mock(name="part")
        part.partname.relative_ref.return_value = "../media/image1.png"
        rels.add_relationship(reltype="http://rt-image", target=part, rId="rId2")
        return rels

    @pytest.fixture
    def _reltype(self):
        return RT.SLIDE

    @pytest.fixture
    def reltype(self):
        return "http://rel/type"

    @pytest.fixture
    def _rId(self):
        return "rId6"

    @pytest.fixture
    def _target_part(self, request):
        return loose_mock(request)

    @pytest.fixture
    def url(self):
        return "https://github.com/scanny/python-pptx"


class Describe_Relationship(object):
    """Unit-test suite for `pptx.opc.package._Relationship` objects."""

    def it_remembers_construction_values(self):
        # test data --------------------
        rId = "rId9"
        reltype = "reltype"
        target = Mock(name="target_part")
        external = False
        # exercise ---------------------
        rel = _Relationship(rId, reltype, target, None, external)
        # verify -----------------------
        assert rel.rId == rId
        assert rel.reltype == reltype
        assert rel.target_part == target
        assert rel.is_external == external

    def it_should_raise_on_target_part_access_on_external_rel(self):
        rel = _Relationship(None, None, None, None, external=True)
        with pytest.raises(ValueError):
            rel.target_part

    def it_should_have_target_ref_for_external_rel(self):
        rel = _Relationship(None, None, "target", None, external=True)
        assert rel.target_ref == "target"

    def it_should_have_relative_ref_for_internal_rel(self):
        """
        Internal relationships (TargetMode == 'Internal' in the XML) should
        have a relative ref, e.g. '../slideLayouts/slideLayout1.xml', for
        the target_ref attribute.
        """
        part = Mock(name="part", partname=PackURI("/ppt/media/image1.png"))
        baseURI = "/ppt/slides"
        rel = _Relationship(None, None, part, baseURI)  # external=False
        assert rel.target_ref == "../media/image1.png"


class DescribeUnmarshaller(object):
    def it_can_unmarshal_from_a_pkg_reader(
        self,
        pkg_reader_,
        pkg_,
        part_factory_,
        _unmarshal_parts,
        _unmarshal_relationships,
        parts_dict_,
    ):
        Unmarshaller.unmarshal(pkg_reader_, pkg_, part_factory_)

        _unmarshal_parts.assert_called_once_with(pkg_reader_, pkg_, part_factory_)
        _unmarshal_relationships.assert_called_once_with(pkg_reader_, pkg_, parts_dict_)

    def it_can_unmarshal_parts(
        self,
        pkg_reader_,
        pkg_,
        part_factory_,
        parts_dict_,
        partnames_,
        content_types_,
        blobs_,
    ):
        # fixture ----------------------
        partname_, partname_2_ = partnames_
        content_type_, content_type_2_ = content_types_
        blob_, blob_2_ = blobs_
        # exercise ---------------------
        parts = Unmarshaller._unmarshal_parts(pkg_reader_, pkg_, part_factory_)
        # verify -----------------------
        assert part_factory_.call_args_list == [
            call(partname_, content_type_, blob_, pkg_),
            call(partname_2_, content_type_2_, blob_2_, pkg_),
        ]
        assert parts == parts_dict_

    def it_can_unmarshal_relationships(self):
        # test data --------------------
        reltype = "http://reltype"
        # mockery ----------------------
        pkg_reader = Mock(name="pkg_reader")
        pkg_reader.iter_srels.return_value = (
            (
                "/",
                Mock(
                    name="srel1",
                    rId="rId1",
                    reltype=reltype,
                    target_partname="partname1",
                    is_external=False,
                ),
            ),
            (
                "/",
                Mock(
                    name="srel2",
                    rId="rId2",
                    reltype=reltype,
                    target_ref="target_ref_1",
                    is_external=True,
                ),
            ),
            (
                "partname1",
                Mock(
                    name="srel3",
                    rId="rId3",
                    reltype=reltype,
                    target_partname="partname2",
                    is_external=False,
                ),
            ),
            (
                "partname2",
                Mock(
                    name="srel4",
                    rId="rId4",
                    reltype=reltype,
                    target_ref="target_ref_2",
                    is_external=True,
                ),
            ),
        )
        pkg = Mock(name="pkg")
        parts = {}
        for num in range(1, 3):
            name = "part%d" % num
            part = Mock(name=name)
            parts["partname%d" % num] = part
            pkg.attach_mock(part, name)
        # exercise ---------------------
        Unmarshaller._unmarshal_relationships(pkg_reader, pkg, parts)
        # verify -----------------------
        expected_pkg_calls = [
            call.load_rel(reltype, parts["partname1"], "rId1", False),
            call.load_rel(reltype, "target_ref_1", "rId2", True),
            call.part1.load_rel(reltype, parts["partname2"], "rId3", False),
            call.part2.load_rel(reltype, "target_ref_2", "rId4", True),
        ]
        assert pkg.mock_calls == expected_pkg_calls

    # fixtures ---------------------------------------------

    @pytest.fixture
    def blobs_(self, request):
        blob_ = loose_mock(request, spec=str, name="blob_")
        blob_2_ = loose_mock(request, spec=str, name="blob_2_")
        return blob_, blob_2_

    @pytest.fixture
    def content_types_(self, request):
        content_type_ = loose_mock(request, spec=str, name="content_type_")
        content_type_2_ = loose_mock(request, spec=str, name="content_type_2_")
        return content_type_, content_type_2_

    @pytest.fixture
    def part_factory_(self, request, parts_):
        part_factory_ = loose_mock(request, spec=Part)
        part_factory_.side_effect = parts_
        return part_factory_

    @pytest.fixture
    def partnames_(self, request):
        partname_ = loose_mock(request, spec=str, name="partname_")
        partname_2_ = loose_mock(request, spec=str, name="partname_2_")
        return partname_, partname_2_

    @pytest.fixture
    def parts_(self, request):
        part_ = instance_mock(request, Part, name="part_")
        part_2_ = instance_mock(request, Part, name="part_2")
        return part_, part_2_

    @pytest.fixture
    def parts_dict_(self, request, partnames_, parts_):
        partname_, partname_2_ = partnames_
        part_, part_2_ = parts_
        return {partname_: part_, partname_2_: part_2_}

    @pytest.fixture
    def pkg_(self, request):
        return instance_mock(request, Package)

    @pytest.fixture
    def pkg_reader_(self, request, partnames_, content_types_, blobs_):
        partname_, partname_2_ = partnames_
        content_type_, content_type_2_ = content_types_
        blob_, blob_2_ = blobs_
        spart_return_values = (
            (partname_, content_type_, blob_),
            (partname_2_, content_type_2_, blob_2_),
        )
        pkg_reader_ = instance_mock(request, PackageReader)
        pkg_reader_.iter_sparts.return_value = spart_return_values
        return pkg_reader_

    @pytest.fixture
    def _unmarshal_parts(self, request, parts_dict_):
        return method_mock(
            request, Unmarshaller, "_unmarshal_parts", return_value=parts_dict_
        )

    @pytest.fixture
    def _unmarshal_relationships(self, request):
        return method_mock(request, Unmarshaller, "_unmarshal_relationships")
