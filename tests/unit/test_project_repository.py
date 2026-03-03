"""Unit tests for ProjectRepository."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


class TestProjectRepositoryInstantiation:
    """Test ProjectRepository initialization."""

    def test_repository_can_be_instantiated(self):
        """Test that ProjectRepository can be created with session."""
        try:
            from simpa.db.repository import ProjectRepository
            
            mock_session = MagicMock(spec=AsyncSession)
            repo = ProjectRepository(mock_session)
            
            assert repo.session is mock_session
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")


class TestProjectRepositoryCreate:
    """Test ProjectRepository create method."""

    @pytest.mark.asyncio
    async def test_create_project_minimal(self):
        """Test creating project with minimal fields."""
        try:
            from simpa.db.repository import ProjectRepository
            from simpa.db.models import Project
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            mock_session.refresh = AsyncMock()
            
            repo = ProjectRepository(mock_session)
            
            result = await repo.create(project_name="test-project")
            
            # Session.add should be called with a Project instance
            mock_session.add.assert_called_once()
            mock_session.flush.assert_called_once()
            mock_session.refresh.assert_called_once()
            
            # Verify the Project was created
            added_project = mock_session.add.call_args[0][0]
            assert isinstance(added_project, Project)
            assert added_project.project_name == "test-project"
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")

    @pytest.mark.asyncio
    async def test_create_project_with_description(self):
        """Test creating project with description."""
        try:
            from simpa.db.repository import ProjectRepository
            from simpa.db.models import Project
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            mock_session.refresh = AsyncMock()
            
            repo = ProjectRepository(mock_session)
            
            result = await repo.create(
                project_name="my-project",
                description="A test project",
            )
            
            added_project = mock_session.add.call_args[0][0]
            assert added_project.project_name == "my-project"
            assert added_project.description == "A test project"
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")

    @pytest.mark.asyncio
    async def test_create_project_returns_project(self):
        """Test that create returns the created Project."""
        try:
            from simpa.db.repository import ProjectRepository
            from simpa.db.models import Project
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            mock_session.refresh = AsyncMock()
            
            repo = ProjectRepository(mock_session)
            
            # Mock the refresh to set the id
            async def mock_refresh(project):
                project.id = uuid.uuid4()
            
            mock_session.refresh = mock_refresh
            
            result = await repo.create(project_name="test")
            
            assert isinstance(result, Project)
            assert result.id is not None
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")


class TestProjectRepositoryGetById:
    """Test ProjectRepository get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_existing_project(self):
        """Test retrieving existing project by ID."""
        try:
            from simpa.db.repository import ProjectRepository
            from simpa.db.models import Project
            
            project_id = uuid.uuid4()
            expected_project = Project(
                id=project_id,
                project_name="test-project",
            )
            
            # Mock the execute result
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = expected_project
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            repo = ProjectRepository(mock_session)
            result = await repo.get_by_id(project_id)
            
            assert result == expected_project
            assert result.project_name == "test-project"
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")

    @pytest.mark.asyncio
    async def test_get_by_id_nonexistent_project(self):
        """Test retrieving non-existent project returns None."""
        try:
            from simpa.db.repository import ProjectRepository
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            repo = ProjectRepository(mock_session)
            result = await repo.get_by_id(uuid.uuid4())
            
            assert result is None
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")


class TestProjectRepositoryGetByName:
    """Test ProjectRepository get_by_name method."""

    @pytest.mark.asyncio
    async def test_get_by_name_existing(self):
        """Test retrieving project by name."""
        try:
            from simpa.db.repository import ProjectRepository
            from simpa.db.models import Project
            
            expected_project = Project(
                id=uuid.uuid4(),
                project_name="my-project",
            )
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = expected_project
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            repo = ProjectRepository(mock_session)
            result = await repo.get_by_name("my-project")
            
            assert result == expected_project
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")

    @pytest.mark.asyncio
    async def test_get_by_name_nonexistent(self):
        """Test retrieving non-existent project name returns None."""
        try:
            from simpa.db.repository import ProjectRepository
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            repo = ProjectRepository(mock_session)
            result = await repo.get_by_name("nonexistent")
            
            assert result is None
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")


class TestProjectRepositoryList:
    """Test ProjectRepository list method."""

    @pytest.mark.asyncio
    async def test_list_all_projects(self):
        """Test listing all projects."""
        try:
            from simpa.db.repository import ProjectRepository
            from simpa.db.models import Project
            
            projects = [
                Project(id=uuid.uuid4(), project_name="project-1"),
                Project(id=uuid.uuid4(), project_name="project-2"),
            ]
            
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = projects
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            repo = ProjectRepository(mock_session)
            result = await repo.list_all()
            
            assert len(result) == 2
            assert result[0].project_name == "project-1"
            assert result[1].project_name == "project-2"
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")

    @pytest.mark.asyncio
    async def test_list_empty(self):
        """Test listing when no projects exist."""
        try:
            from simpa.db.repository import ProjectRepository
            
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            repo = ProjectRepository(mock_session)
            result = await repo.list_all()
            
            assert result == []
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")

    @pytest.mark.asyncio
    async def test_list_active_only(self):
        """Test listing only active projects."""
        try:
            from simpa.db.repository import ProjectRepository
            from simpa.db.models import Project
            
            active_project = Project(
                id=uuid.uuid4(),
                project_name="active",
                is_active=True,
            )
            
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [active_project]
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            repo = ProjectRepository(mock_session)
            result = await repo.list_active()
            
            assert len(result) == 1
            assert result[0].is_active is True
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")


class TestProjectRepositoryUpdate:
    """Test ProjectRepository update method."""

    @pytest.mark.asyncio
    async def test_update_project(self):
        """Test updating project fields."""
        try:
            from simpa.db.repository import ProjectRepository
            from simpa.db.models import Project
            
            project_id = uuid.uuid4()
            existing = Project(
                id=project_id,
                project_name="old-name",
                description="old desc",
            )
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = existing
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.flush = AsyncMock()
            mock_session.refresh = AsyncMock()
            
            repo = ProjectRepository(mock_session)
            result = await repo.update(
                project_id,
                description="new desc",
            )
            
            assert result.description == "new desc"
            mock_session.flush.assert_called_once()
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(self):
        """Test updating non-existent project returns None."""
        try:
            from simpa.db.repository import ProjectRepository
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            repo = ProjectRepository(mock_session)
            result = await repo.update(uuid.uuid4(), description="new")
            
            assert result is None
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")


class TestProjectRepositorySoftDelete:
    """Test ProjectRepository soft delete."""

    @pytest.mark.asyncio
    async def test_soft_delete_existing(self):
        """Test soft deleting existing project."""
        try:
            from simpa.db.repository import ProjectRepository
            from simpa.db.models import Project
            
            project_id = uuid.uuid4()
            existing = Project(
                id=project_id,
                project_name="test",
                is_active=True,
            )
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = existing
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.flush = AsyncMock()
            
            repo = ProjectRepository(mock_session)
            result = await repo.soft_delete(project_id)
            
            assert result is True
            assert existing.is_active is False
            mock_session.flush.assert_called_once()
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")

    @pytest.mark.asyncio
    async def test_soft_delete_nonexistent(self):
        """Test soft deleting non-existent project returns False."""
        try:
            from simpa.db.repository import ProjectRepository
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.execute = AsyncMock(return_value=mock_result)
            
            repo = ProjectRepository(mock_session)
            result = await repo.soft_delete(uuid.uuid4())
            
            assert result is False
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")


class TestProjectRepositoryAddPrompt:
    """Test ProjectRepository add_prompt_to_project method."""

    @pytest.mark.asyncio
    async def test_add_prompt_to_project(self):
        """Test adding a prompt reference to a project."""
        try:
            from simpa.db.repository import ProjectRepository
            from simpa.db.models import Project, RefinedPrompt
            
            project = Project(id=uuid.uuid4(), project_name="test")
            prompt = RefinedPrompt(
                id=uuid.uuid4(),
                agent_type="developer",
                original_prompt="test",
                refined_prompt="refined",
            )
            
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = project
            
            mock_session = MagicMock(spec=AsyncSession)
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.flush = AsyncMock()
            
            repo = ProjectRepository(mock_session)
            
            with patch.object(project.prompts, 'append', MagicMock()) as mock_append:
                result = await repo.add_prompt(project.id, prompt.id)
                
                assert result is True
                mock_session.flush.assert_called_once()
            
        except ImportError:
            pytest.skip("ProjectRepository not yet implemented")
