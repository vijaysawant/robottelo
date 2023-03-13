"""Test for LEAPP cli

:Requirement: leapp

:CaseLevel: Acceptance

:CaseComponent: LEAPP

:Team: Rocket

:TestType: Functional

:CaseImportance: High

:CaseAutomation: Automated

:Upstream: No
"""
import pytest
# from robottelo.constants import PRDS
# from robottelo.constants import REPO_TYPE
# from robottelo.constants import REPOS
# from robottelo.constants import REPOSET
from robottelo.config import settings

@pytest.mark.no_containers
@pytest.mark.parametrize('target_version', [("9.0")])
@pytest.mark.rhel_ver_match('8')
def test_upgrade_rhel8_to_rehl9(target_sat, module_org, module_product,
                                module_cv, module_lce, module_ak_with_cv,
                                rhel_contenthost, target_version):
    """Test upgrade from RHEL8.7 to RHEL9.0 using LEAPP utility
    :steps:
        1. Import Manifest
        2. Create content view, Activation key, Repositories and Sync created repo
        3. Register the host
        4. Enable RHEL8 BaseOS and AppStream repos
        5. Run leapp pre-upgrade and leapp upgrade
    :expectedresults:
        1. Verify host upgraded successfully to RHEL9
    """
    # Preparing a Satellite-registered system
    # 1. Import a subscription manifest (with RHEL 9 repositories into Satellite Server)
    target_sat.upload_manifest(module_org)
    # 2. Create content view, Activation key, Repositories and Sync created repo
    cv = module_cv
    ak = module_ak_with_cv

    # rhel8_bos_repo = target_sat.api.Repository(
    #     name=REPOS['rhel8_bos']['name'],
    #     url=settings.repos.rhel8_os.baseos,
    #     content_type=REPO_TYPE['yum'],
    #     product=module_product
    # ).create()
    # rhel8_bos_repo.sync(timeout=600)
    #
    # rhel8_aps_repo = target_sat.api.Repository(
    #     name=REPOS['rhel8_aps']['name'],
    #     url=settings.repos.rhel8_os.appstream,
    #     content_type=REPO_TYPE['yum'],
    #     product=module_product
    # ).create()
    # rhel8_aps_repo.sync(timeout=600)
    #
    # rhel9_bos_repo = target_sat.api.Repository(
    #     name=REPOS['rhel9_bos']['name'],
    #     url=settings.repos.rhel9_os.baseos,
    #     content_type=REPO_TYPE['yum'],
    #     product=module_product
    # ).create()
    # rhel9_bos_repo.sync(timeout=600)
    #
    # rhel9_aps_repo = target_sat.api.Repository(
    #     name=REPOS['rhel9_aps']['name'],
    #     url=settings.repos.rhel9_os.appstream,
    #     content_type=REPO_TYPE['yum'],
    #     product=module_product
    # ).create()
    # rhel9_aps_repo.sync(timeout=600)

    # # 3. Register Host
    rhel_contenthost.install_katello_ca(target_sat)
    rhel_contenthost.register_contenthost(org=module_org.label, activation_key=ak.name)
    assert rhel_contenthost.subscribed

    # Preupgrade check
    # Remove directory if in-place upgrade already performed from RHEL7 to RHEL8
    rhel_contenthost.run("rm -rf /root/tmp_leapp_py3")
    # 4. Enable RHEL8 and RHEL9 repos for upgrade
    # rhel8_contenthost.run("subscription-manager repos --enable rhel-8-for-x86_64-baseos-rpms")
    # rhel8_contenthost.run("subscription-manager repos --enable rhel-8-for-x86_64-appstream-rpms")

    # 5. Update all packages and install Leapp utility
    rhel_contenthost.run("yum clean all")
    # rhel8_contenthost.run("yum repolist")
    rhel_contenthost.create_custom_repos(
        baseos=settings.repos.rhel8_os.baseos,
        appstream=settings.repos.rhel8_os.appstream,
    )
    # rhel_contenthost.create_custom_repos(
    #     baseos=settings.repos.rhel9_os.baseos,
    #     appstream=settings.repos.rhel9_os.appstream,
    # )
    rhel_contenthost.run("subscription-manager release --set 8.7")
    result = rhel_contenthost.run("dnf update -y")
    assert result.stdout == 0
    rhel_contenthost.run("yum install leapp-upgrade")

    rhel_contenthost.run(f"leapp preupgrade --target {target_version}")
    rhel_contenthost.run('curl -k "https://gitlab.cee.redhat.com/oamg/leapp-data/-/raw/stage/data/{repomap.json,pes-events.json,device_driver_deprecation_data.json}" -o "/etc/leapp/files/#1"')
    rhel_contenthost.run(f"leapp preupgrade --target {target_version}")
    # TODO
    # Download below LEAPP data to /etc/leapp/files/
    # repomap.json, pes-events.json, device_driver_deprecation_data.json

    # get os version from hosts.py
    # os_version function