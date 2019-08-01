"""Repository."""
# pylint: disable=broad-except, bad-continuation, no-member
import pathlib
from distutils.version import LooseVersion
from integrationhelper import Validate, Logger
from ..hacsbase import Hacs
from ..hacsbase.backup import Backup
from ..handler.download import async_download_file, async_save_file


RERPOSITORY_CLASSES = {}


def register_repository_class(cls):
    """Register class."""
    RERPOSITORY_CLASSES[cls.category] = cls
    return cls


class RepositoryVersions:
    """Versions."""

    available = None
    available_commit = None
    installed = None
    installed_commit = None


class PendingActions:
    """Pending actions."""

    restart = False
    upgrade = False


class RepositoryStatus:
    """Repository status."""

    pending = None
    hide = False
    installed = False
    last_updated = None
    new = True
    selected_tag = None
    show_beta = False
    track = True
    updated_info = False


class RepositoryInformation:
    """RepositoryInformation."""

    additional_info = None
    authors = []
    category = None
    default_branch = None
    description = ""
    full_name = None
    homeassistant_version = None
    last_updated = None
    uid = None
    info = None
    name = None
    topics = []


class RepositoryReleases:
    """RepositoyReleases."""

    last_release = None
    last_release_object = None
    published_tags = []
    releases = False


class RepositoryPath:
    """RepositoryPath."""

    local = None
    remote = None


class RepositoryContent:
    """RepositoryContent."""

    path = None
    files = []
    objects = []
    single = False


class HacsRepository(Hacs):
    """HacsRepository."""

    def __init__(self):
        """Set up HacsRepository."""

        self.content = RepositoryContent()
        self.content.path = RepositoryPath()
        self.information = RepositoryInformation()
        self.repository_object = None
        self.status = RepositoryStatus()
        self.status.pending = PendingActions()
        self.validate = Validate()
        self.releases = RepositoryReleases()
        self.versions = RepositoryVersions()
        self.logger = None

    @property
    def ref(self):
        """Return the ref."""
        if self.status.selected_tag is not None:
            if self.status.selected_tag == self.information.default_branch:
                return self.information.default_branch
            return "tags/{}".format(self.status.selected_tag)

        if self.releases.releases:
            return "tags/{}".format(self.versions.available)

        return self.information.default_branch

    @property
    def custom(self):
        """Return flag if the repository is custom."""
        if self.information.full_name.split("/")[0] in [
            "custom-components",
            "custom-cards",
        ]:
            return False
        if self.information.full_name in self.common.default:
            return False
        return True

    @property
    def can_install(self):
        """Return bool if repository can be installed."""
        if self.information.homeassistant_version is not None:
            if self.releases.releases:
                if LooseVersion(self.system.ha_version) < LooseVersion(
                    self.information.homeassistant_version
                ):
                    return False
        return True

    @property
    def display_name(self):
        """Return display name."""
        name = None
        if self.information.category == "integration":
            if self.manifest is not None:
                name = self.manifest["name"]

        if name is not None:
            return name

        if self.information.name:
            name = self.information.name.replace("-", " ").replace("_", " ").title()

        if name is not None:
            return name

        name = self.information.full_name

        return name

    @property
    def display_status(self):
        """Return display_status."""
        if self.status.new:
            status = "new"
        elif self.status.pending.restart:
            status = "pending-restart"
        elif self.status.pending.upgrade:
            status = "pending-upgrade"
        elif self.status.installed:
            status = "installed"
        else:
            status = "default"
        return status

    @property
    def display_status_description(self):
        """Return display_status_description."""
        description = {
            "default": "Not installed.",
            "pending-restart": "Restart pending.",
            "pending-upgrade": "Upgrade pending.",
            "installed": "No action required.",
            "new": "This is a newly added repository.",
        }
        return description[self.display_status]

    @property
    def display_authors(self):
        """Return display_authors"""
        if self.repository.authors:
            if self.repository.information.category == "integration":
                authors = """
                <tr class="hacs-table-row repository">
                    <td class="repository">
                        <b>Author(s):</b>
                    </td>
                    <td class="repository">
                """
                for author in self.information.authors:
                    if "@" in author:
                        author = author.split("@")[-1]
                    authors += f"<a rel='noreferrer' href='https://github.com/{author}' target='_blank' style='color: var(--primary-color) !important; margin: 2'> @{author}</a>"
                authors += "</td></tr>"
            else:
                authors = f"""
                <tr class="hacs-table-row repository">
                    <td class="repository">
                        <b>Author:</b>
                    </td>
                    <td class="repository">
                        {self.information.authors}
                    </td>
                </tr>
                """
        else:
            authors = ""
        return authors

    @property
    def display_installed_version(self):
        """Return display_authors"""
        if self.versions.installed is not None:
            installed = self.versions.installed
        else:
            if self.versions.installed_commit is not None:
                installed = self.versions.installed_commit
            else:
                installed = ""
        return installed

    @property
    def display_available_version(self):
        """Return display_authors"""
        if self.versions.available is not None:
            available = self.versions.available
        else:
            if self.versions.available_commit is not None:
                available = self.versions.available_commit
            else:
                available = ""
        return available

    @property
    def display_version_or_commit(self):
        """Does the repositoriy use releases or commits?"""
        if self.releases.releases:
            version_or_commit = "version"
        else:
            version_or_commit = "commit"
        return version_or_commit

    @property
    def main_action(self):
        """Return the main action."""
        actions = {
            "new": "INSTALL",
            "default": "INSTALL",
            "installed": "REINSTALL",
            "pending-restart": "REINSTALL",
            "pending-upgrade": "UPGRADE",
        }
        return actions[self.display_status]

    async def common_validate(self):
        """Common validation steps of the repository."""
        # Attach helpers
        self.validate.errors = []
        self.logger = Logger(
            f"hacs.repository.{self.information.category}.{self.information.full_name}"
        )

        # Step 1: Make sure the repository exist.
        self.logger.debug("Checking repository.")
        try:
            self.repository_object = await self.github.get_repo(
                self.information.full_name
            )
        except Exception as exception:  # Gotta Catch 'Em All
            if not self.system.status.startup:
                self.logger.error(exception)
            self.validate.errors.append("Repository does not exist.")
            return

        # Step 2: Make sure the repository is not archived.
        if self.repository_object.archived:
            self.validate.errors.append("Repository is archived.")
            return

        # Step 3: Make sure the repository is not in the blacklist.
        if self.information.full_name in self.common.blacklist:
            self.validate.errors.append("Repository is in the blacklist.")
            return

        # Step 4: default branch
        self.information.default_branch = self.repository_object.default_branch

        # Step 5: Get releases.
        await self.get_releases()

        # Set repository name
        self.information.name = self.information.full_name.split("/")[1]

    async def common_registration(self):
        """Common registration steps of the repository."""
        # Attach logger
        if self.logger is None:
            self.logger = Logger(
                f"hacs.repository.{self.information.category}.{self.information.full_name}"
            )

        # Attach repository
        if self.repository_object is None:
            self.repository_object = await self.github.get_repo(
                self.information.full_name
            )

        # Set id
        self.information.uid = str(self.repository_object.id)

        # Set topics
        self.information.topics = self.repository_object.topics

        # Set description
        if self.repository_object.description:
            self.information.description = self.repository_object.description

    async def common_update(self):
        """Common information update steps of the repository."""
        # Attach logger
        if self.logger is None:
            self.logger = Logger(
                f"hacs.repository.{self.information.category}.{self.information.full_name}"
            )

        # Attach repository
        self.repository_object = await self.github.get_repo(self.information.full_name)

        # Update description
        if self.repository_object.description:
            self.information.description = self.repository_object.description

        # Update default branch
        if self.information.full_name != "custom-components/hacs":
            self.information.default_branch = self.repository_object.default_branch
        else:
            self.information.default_branch = "next"

        # Update last available commit
        await self.repository_object.set_last_commit()
        self.versions.available_commit = self.repository_object.last_commit

        # Update last updaeted
        self.information.last_updated = self.repository_object.pushed_at

        # Update topics
        self.information.topics = self.repository_object.topics

        # Update "info.md"
        await self.get_info_md_content()

        # Update releases
        await self.get_releases()

        # Set pending upgrade
        if self.status.installed:
            if self.versions.installed:
                self.status.pending.upgrade = bool(
                    self.versions.available != self.versions.installed
                )
            else:
                self.status.pending.upgrade = bool(
                    self.versions.available_commit != self.versions.installed_commit
                )
        else:
            self.status.pending.upgrade = False

    async def install(self):
        """Common installation steps of the repository."""
        self.validate.errors = []

        await self.update_repository()

        if self.status.installed:
            backup = Backup(self.content.path.local)
            backup.create()

        validate = await self.download_content(
            self.validate, self.content.path.remote, self.content.path.local, self.ref
        )

        if validate.errors:
            for error in validate.errors:
                self.logger.error(error)
            if self.status.installed:
                backup.restore()

        if self.status.installed:
            backup.cleanup()

        if validate.success:
            if self.information.full_name not in self.common.installed:
                self.common.installed.append(self.information.full_name)
            self.status.installed = True
            self.versions.installed_commit = self.versions.available_commit

            if self.status.selected_tag is not None:
                self.versions.installed = self.status.selected_tag
            else:
                self.versions.installed = self.versions.available

            if self.information.category == "integration":
                if self.config_flow:
                    await self.reload_custom_components()
                else:
                    self.status.pending.restart = True
                await self.reload_custom_components()

    async def download_content(self, validate, directory_path, local_directory, ref):
        """Download the content of a directory."""
        try:
            # Get content
            if self.content.single:
                contents = self.content.objects
            else:
                contents = await self.repository_object.get_contents(
                    directory_path, self.ref
                )

            for content in contents:
                if content.type == "dir" and self.content.path.remote != "":
                    await self.download_content(
                        validate, content.path, local_directory, ref
                    )
                    continue
                if self.information.category == "plugin":
                    if not content.name.endswith(".js"):
                        if self.content.path.remote != "dist":
                            continue

                self.logger.debug(f"Downloading {content.name}")

                filecontent = await async_download_file(self.hass, content.download_url)

                if filecontent is None:
                    validate.errors.append(f"[{content.name}] was not downloaded.")
                    continue

                # Save the content of the file.
                if self.content.single:
                    local_directory = self.content.path.local
                else:
                    _content_path = content.path
                    _content_path = _content_path.replace(
                        f"{self.content.path.remote}/", ""
                    )

                    local_directory = f"{self.content.path.local}/{_content_path}"
                    local_directory = local_directory.split("/")
                    del local_directory[-1]
                    local_directory = "/".join(local_directory)

                # Check local directory
                pathlib.Path(local_directory).mkdir(parents=True, exist_ok=True)

                local_file_path = f"{local_directory}/{content.name}"
                result = await async_save_file(local_file_path, filecontent)
                if result:
                    self.logger.info(f"download of {content.name} complete")
                    continue
                validate.errors.append(f"[{content.name}] was not downloaded.")

        except SystemError:
            pass
        return validate

    async def get_info_md_content(self):
        """Get the content of info.md"""
        from ..handler.template import render_template

        info = None
        info_files = ["info", "info.md"]
        try:
            root = await self.repository_object.get_contents("", self.ref)
            for file in root:
                if file.name.lower() in info_files:
                    info = await self.repository_object.get_contents(
                        file.name, self.ref
                    )
                    break
            if info is None:
                self.information.additional_info = ""
            else:
                info = await self.github.render_markdown(info.content)
                info = info.replace("&lt;", "<")
                info = info.replace("<h3>", "<h6>").replace("</h3>", "</h6>")
                info = info.replace("<h2>", "<h5>").replace("</h2>", "</h5>")
                info = info.replace("<h1>", "<h4>").replace("</h1>", "</h4>")
                info = info.replace("<code>", "<code class='codeinfo'>")
                info = info.replace(
                    '<a href="http', '<a rel="noreferrer" target="_blank" href="http'
                )
                info = info.replace("<ul>", "")
                info = info.replace("</ul>", "")
                info += "</br>"
                self.information.additional_info = render_template(info, self)

        except Exception:  # Gotta Catch 'Em All
            self.information.additional_info = ""

    async def get_releases(self):
        """Get repository releases."""
        if self.status.show_beta:
            temp = await self.repository_object.get_releases(prerelease=True)
        else:
            temp = await self.repository_object.get_releases(prerelease=False)

        if not temp:
            return

        self.releases.releases = True

        self.releases.published_tags = []

        for release in temp:
            self.releases.published_tags.append(release.tag_name)

        self.releases.last_release_object = temp[0]
        if self.status.selected_tag is not None:
            if self.status.selected_tag != self.information.default_branch:
                for release in temp:
                    if release.tag_name == self.status.selected_tag:
                        self.releases.last_release_object = release
                        break
        self.versions.available = temp[0].tag_name

    def remove(self):
        """Run remove tasks."""
        # Attach logger
        if self.logger is None:
            self.logger = Logger(
                f"hacs.repository.{self.information.category}.{self.information.full_name}"
            )
        self.logger.info("Starting removal")

        if self.information.uid in self.common.installed:
            self.common.installed.remove(self.information.uid)
        for repository in self.repositories:
            if repository.information.uid == self.repository_id:
                self.repositories.remove(repository)

    async def uninstall(self):
        """Run uninstall tasks."""
        # Attach logger
        if self.logger is None:
            self.logger = Logger(
                f"hacs.repository.{self.information.category}.{self.information.full_name}"
            )
        self.logger.info("Uninstalling")
        await self.remove_local_directory()
        self.status.installed = False
        if self.information.category == "integration":
            self.status.pending.restart = True
        self.versions.installed = None
        self.versions.installed_commit = None

    async def remove_local_directory(self):
        """Check the local directory."""
        import os
        import shutil
        from asyncio import sleep

        try:
            if self.information.category == "python_script":
                local_path = "{}/{}.py".format(self.local_path, self.name)
            elif self.information.category == "theme":
                local_path = "{}/{}.yaml".format(self.local_path, self.name)
            else:
                local_path = self.local_path

            if os.path.exists(local_path):
                self.logger.debug(f"Removing {local_path}")

                if self.information.category in ["python_script", "theme"]:
                    os.remove(local_path)
                else:
                    shutil.rmtree(local_path)

                while os.path.exists(local_path):
                    await sleep(1)

        except Exception as exception:
            self.logger.debug(f"Removing {local_path} failed with {exception}")
            return
